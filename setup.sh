#!/bin/bash

# NYC Taxi Pipeline Setup Script
# Automated setup and verification for the complete pipeline

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Header
echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║         NYC Taxi Pipeline - Automated Setup               ║
║                                                           ║
║  This script will set up and verify your pipeline        ║
║  environment, including Docker, dependencies, and        ║
║  initial data processing.                                ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Step 1: Check prerequisites
print_step "Step 1: Checking prerequisites..."

if command_exists docker; then
    DOCKER_VERSION=$(docker --version)
    print_success "Docker found: $DOCKER_VERSION"
else
    print_error "Docker not found. Please install Docker Desktop first."
    echo "Download from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if command_exists docker-compose; then
    COMPOSE_VERSION=$(docker-compose --version)
    print_success "Docker Compose found: $COMPOSE_VERSION"
else
    print_error "Docker Compose not found. Please install Docker Compose."
    exit 1
fi

if command_exists python3; then
    PYTHON_VERSION=$(python3 --version)
    print_success "Python found: $PYTHON_VERSION"
else
    print_warning "Python3 not found (optional for local development)"
fi

if command_exists make; then
    print_success "Make found"
else
    print_warning "Make not found (optional, you can use docker-compose directly)"
fi

# Step 2: Create directory structure
print_step "Step 2: Creating directory structure..."

mkdir -p data/{raw,bronze,silver,gold}
mkdir -p data/raw/{yellow_trips,zone_lookup}
mkdir -p logs
mkdir -p spark/{jobs,common,tests}
mkdir -p airflow/dags
mkdir -p database
mkdir -p terraform
mkdir -p docs
mkdir -p .github/workflows

print_success "Directory structure created"

# Step 3: Create environment file
print_step "Step 3: Setting up environment configuration..."

if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Storage Configuration
STORAGE_TYPE=local

# PostgreSQL Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=nyc_taxi
POSTGRES_USER=taxi_user
POSTGRES_PASSWORD=taxi_pass

# Spark Configuration
SPARK_MASTER_HOST=spark-master
SPARK_MASTER_PORT=7077
SPARK_WORKER_CORES=2
SPARK_WORKER_MEMORY=2g

# Pipeline Parameters
DEFAULT_YEAR=2023
DEFAULT_MONTHS=1
EOF
    print_success "Environment file created (.env)"
else
    print_warning ".env file already exists, skipping..."
fi

# Step 4: Check Docker daemon
print_step "Step 4: Verifying Docker daemon..."

if docker info >/dev/null 2>&1; then
    print_success "Docker daemon is running"
else
    print_error "Docker daemon is not running. Please start Docker Desktop."
    exit 1
fi

# Step 5: Check disk space
print_step "Step 5: Checking disk space..."

if command_exists df; then
    AVAILABLE_SPACE=$(df -h . | awk 'NR==2 {print $4}')
    print_success "Available disk space: $AVAILABLE_SPACE"
    print_warning "Note: Full year processing requires ~60GB free space"
else
    print_warning "Could not check disk space"
fi

# Step 6: Build Docker images
print_step "Step 6: Building Docker images (this may take 5-10 minutes)..."

if [ -f docker-compose.yml ]; then
    docker-compose build --no-cache
    print_success "Docker images built successfully"
else
    print_error "docker-compose.yml not found in current directory"
    exit 1
fi

# Step 7: Start services
print_step "Step 7: Starting services..."

docker-compose up -d

print_success "Services started"
echo "Waiting 30 seconds for services to initialize..."
sleep 30

# Step 8: Verify services are running
print_step "Step 8: Verifying services..."

check_service() {
    SERVICE_NAME=$1
    if docker-compose ps | grep "$SERVICE_NAME" | grep -q "Up"; then
        print_success "$SERVICE_NAME is running"
        return 0
    else
        print_error "$SERVICE_NAME is not running"
        return 1
    fi
}

ALL_SERVICES_OK=true
check_service "spark-master" || ALL_SERVICES_OK=false
check_service "spark-worker" || ALL_SERVICES_OK=false
check_service "postgres" || ALL_SERVICES_OK=false
check_service "airflow-webserver" || ALL_SERVICES_OK=false
check_service "airflow-scheduler" || ALL_SERVICES_OK=false

if [ "$ALL_SERVICES_OK" = false ]; then
    print_error "Some services failed to start. Check logs with: docker-compose logs"
    exit 1
fi

# Step 9: Verify PostgreSQL is healthy
print_step "Step 9: Checking PostgreSQL health..."

for i in {1..10}; do
    if docker-compose exec -T postgres pg_isready -U taxi_user >/dev/null 2>&1; then
        print_success "PostgreSQL is healthy"
        break
    else
        if [ $i -eq 10 ]; then
            print_error "PostgreSQL did not become healthy in time"
            exit 1
        fi
        echo "Waiting for PostgreSQL... ($i/10)"
        sleep 3
    fi
done

# Step 10: Run a quick test
print_step "Step 10: Running quick validation test..."

# Test database connection
if docker-compose exec -T postgres psql -U taxi_user -d nyc_taxi -c "SELECT 1" >/dev/null 2>&1; then
    print_success "Database connection successful"
else
    print_error "Database connection failed"
    exit 1
fi

# Step 11: Display service URLs
print_step "Step 11: Setup complete! Service URLs:"
echo ""
echo -e "${GREEN}✓ Spark Master UI:${NC}  http://localhost:8080"
echo -e "${GREEN}✓ Airflow UI:${NC}       http://localhost:8081 (admin/admin)"
echo -e "${GREEN}✓ PostgreSQL:${NC}       localhost:5432 (taxi_user/taxi_pass)"
echo ""

# Step 12: Offer to run sample pipeline
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
read -p "Would you like to run a sample pipeline now? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_step "Running sample pipeline for January 2023..."
    echo ""
    
    # Run bronze ingestion
    print_step "Phase 1/3: Bronze ingestion (downloading data)..."
    docker-compose exec -T spark-master spark-submit \
        /opt/spark-app/jobs/bronze_ingestion.py \
        --year 2023 --months 1 --storage-type local
    
    if [ $? -eq 0 ]; then
        print_success "Bronze ingestion completed"
    else
        print_error "Bronze ingestion failed"
        exit 1
    fi
    
    # Run dimensional transform
    print_step "Phase 2/3: Dimensional transformation..."
    docker-compose exec -T spark-master spark-submit \
        /opt/spark-app/jobs/dimensional_transform.py \
        --year 2023 --months 1 --storage-type local
    
    if [ $? -eq 0 ]; then
        print_success "Dimensional transformation completed"
    else
        print_error "Dimensional transformation failed"
        exit 1
    fi
    
    # Run database loader
    print_step "Phase 3/3: Loading to database..."
    docker-compose exec -T spark-master spark-submit \
        --jars /opt/spark/jars/postgresql-42.7.8.jar \
        /opt/spark-app/jobs/db_loader.py \
        --year 2023 --months 1 --storage-type local
    
    if [ $? -eq 0 ]; then
        print_success "Database loading completed"
    else
        print_error "Database loading failed"
        exit 1
    fi
    
    # Query results
    print_step "Querying results..."
    echo ""
    docker-compose exec -T postgres psql -U taxi_user -d nyc_taxi -c \
        "SELECT COUNT(*) as total_trips, 
                ROUND(AVG(fare_amount)::numeric, 2) as avg_fare,
                ROUND(SUM(total_amount)::numeric, 2) as total_revenue
         FROM fact_taxi_trips;"
    
    echo ""
    print_success "Sample pipeline completed successfully!"
fi

# Final instructions
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Setup Complete!${NC} Here are your next steps:"
echo ""
echo "📊 Query your data:"
echo "   docker-compose exec postgres psql -U taxi_user -d nyc_taxi"
echo ""
echo "🔄 Run pipeline for more months:"
echo "   make run-pipeline YEAR=2023 MONTHS=1,2,3"
echo ""
echo "📈 View Spark jobs:"
echo "   Open http://localhost:8080"
echo ""
echo "🎯 Use Airflow:"
echo "   Open http://localhost:8081 (admin/admin)"
echo ""
echo "📖 Read full documentation:"
echo "   cat README.md"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Happy Data Engineering! 🚀${NC}"
echo ""