# General Logistics Co (GLC)

> A production-grade mock business simulation platform demonstrating a full-stack, microservices-based enterprise system for a widget retail and distribution company. Designed to serve as a baseline for measuring and demonstrating the value of AI-powered automation across real business operations.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Business Context](#business-context)
3. [System Architecture](#system-architecture)
4. [Microservices](#microservices)
5. [Data Architecture](#data-architecture)
6. [Infrastructure & Tooling](#infrastructure--tooling)
7. [Directory Structure](#directory-structure)
8. [Technology Stack](#technology-stack)
9. [Key Business Operations (AI Automation Targets)](#key-business-operations-ai-automation-targets)
10. [Getting Started](#getting-started)
11. [Environment Variables](#environment-variables)
12. [Development Guide](#development-guide)

---

## Project Overview

General Logistics Co (GLC) is a fully simulated small-to-mid-sized enterprise that buys widgets from suppliers, warehouses them across fulfillment centers, sells them to customers via a web storefront, and handles all the back-office operations a real company would require: payroll, accounting, sales tax, supplier relationships, shipping, inventory, and more.

The system is intentionally built to resemble how a real company's software ecosystem grows organically: multiple specialized services, heterogeneous databases, manual human workflows, and a realistic volume of operational noise. This makes it an ideal proving ground for demonstrating where AI and automation can eliminate toil, reduce errors, and save measurable employee hours per day.

Every service is designed to reflect real business logic and data flows. When an order is placed, inventory is decremented, payment is captured, tax is withheld, a fulfillment job is queued, a shipping label is generated, accounting entries are posted, and the customer is notified, just like in real life.

---

## Business Context

### What GLC Does

- **Sells widgets** to retail customers via an e-commerce website
- **Procures widgets** from a pool of fictional suppliers via purchase orders
- **Warehouses inventory** across multiple fictional fulfillment centers
- **Ships orders** using fictional carrier integrations (rate-shopping, label generation, tracking)
- **Employs a workforce** with salaries, departments, roles, and a biweekly payroll cycle
- **Handles all financial operations**: accounts payable/receivable, general ledger, reconciliation, monthly close
- **Collects and remits sales tax** across multiple fictional jurisdictions
- **Manages customer relationships**: accounts, purchase history, support tickets, returns

### Widget Product Line

GLC sells a catalog of widgets in multiple categories, sizes, and configurations. Products have:
- SKUs with variant attributes (size, color, material)
- MSRP and variable promotional pricing
- Reorder thresholds and supplier lead times
- Per-unit cost basis tracked for COGS accounting

### Simulated Business Volume

A `customer_simulator` service drives a realistic, variable flow of customer activity:
- Configurable orders-per-hour with day-of-week and time-of-day patterns
- Realistic cart abandonment, returns, and disputes
- Occasional bulk/wholesale orders
- Seasonal spikes (configurable)

A `supplier_simulator` service models supplier behavior:
- Responds to purchase orders with confirmations and invoices
- Ships inventory with variable lead times
- Occasionally sends partial shipments, backorders, or incorrect quantities

---

## System Architecture

```
                          ┌─────────────────────────────────────────────────┐
                          │                  External World                 │
                          │   (Customers via Browser / Supplier Responses)  │
                          └──────────────────────┬──────────────────────────┘
                                                 │
                          ┌──────────────────────▼──────────────────────────┐
                          │                  API Gateway                    │
                          │         (routing, auth, rate limiting)          │
                          └──────┬──────────────────────────────┬───────────┘
                                 │                              │
              ┌──────────────────▼───────┐          ┌───────────▼───────────────┐
              │      Website Service     │          │    Internal Service Mesh  │
              │  (storefront + admin UI) │          │  (service-to-service RPC) │
              └──────────────────────────┘          └───────────────────────────┘
                                                               │
          ┌────────────────────────────────────────────────────┼────────────────────────────────────────────────────┐
          │                          │                         │                         │                          │
  ┌───────▼──────┐         ┌─────────▼──────┐         ┌─────────▼──────┐         ┌───────▼────────┐         ┌───────▼────────┐
  │   Customer   │         │    Product     │         │    Order       │         │   Inventory    │         │   Fulfillment  │
  │   Service    │         │    Service     │         │    Service     │         │    Service     │         │    Service     │
  └──────────────┘         └────────────────┘         └────────────────┘         └────────────────┘         └────────────────┘
          │                          │                         │                         │                          │
  ┌───────▼──────┐         ┌─────────▼──────┐         ┌────────▼───────┐         ┌───────▼────────┐         ┌───────▼────────┐
  │   Payment    │         │   Shipping     │         │     Tax        │         │   Accounting   │         │   Supplier     │
  │   Service    │         │   Service      │         │    Service     │         │    Service     │         │   Service      │
  └──────────────┘         └────────────────┘         └────────────────┘         └────────────────┘         └────────────────┘
          │                          │                         │                                                  
  ┌───────▼──────┐         ┌─────────▼──────┐         ┌────────▼───────┐
  │  Payroll &   │         │  Notification  │         │   Reporting    │
  │  HR Service  │         │   Service      │         │   Service      │
  └──────────────┘         └────────────────┘         └────────────────┘

                    ┌──────────────────────────────────────────────────────────┐
                    │                  Shared Infrastructure                   │
                    │   PostgreSQL  │  MongoDB  │  Redis  │  Message Queue     │
                    └──────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────────────────────────────┐
                    │                  Simulator Services                      │
                    │         customer_simulator  │  supplier_simulator        │
                    └──────────────────────────────────────────────────────────┘
```

All services communicate via REST (HTTP) internally. Redis pub/sub and list-based queues handle asynchronous event propagation (e.g., order placed → fulfillment queued → shipping label requested → customer notified). Everything runs in Docker containers orchestrated by Docker Compose.

---

## Microservices

### `website`
**Type:** FastAPI + Uvicorn + Jinja2 + TailwindCSS  
**Port:** 8000  
**Purpose:** Customer-facing e-commerce storefront and internal admin dashboard.

- **Storefront:** Product browsing, search, cart, checkout, order tracking, account management
- **Admin Dashboard:** Order management UI, inventory views, employee directory, reports viewer
- Renders server-side HTML templates via Jinja2; styled with TailwindCSS
- Communicates with backend services via the API Gateway
- Session management via Redis

---

### `api_gateway`
**Type:** FastAPI + Uvicorn  
**Port:** 8080  
**Purpose:** Single ingress point for all external and cross-service HTTP traffic.

- Route requests to appropriate microservices
- JWT-based authentication and session validation
- Rate limiting (backed by Redis)
- Request logging and correlation ID injection
- Basic circuit breaker logic for downstream service failures

---

### `customer_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8001  
**Database:** PostgreSQL (accounts, addresses, payment methods) + MongoDB (activity logs, preferences, support ticket history)  
**Purpose:** Customer identity, profile, and relationship management.

- Customer registration, login, password reset
- Address book management
- Purchase history and account statement
- Support ticket creation and status tracking
- Customer segmentation tags (loyalty tier, wholesale flag, etc.)

---

### `product_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8002  
**Database:** MongoDB (catalog, attributes, images, descriptions) + PostgreSQL (pricing, promotions)  
**Cache:** Redis (product detail pages, search results)  
**Purpose:** Widget product catalog management.

- Full product catalog with variants (SKU-level)
- Pricing engine: MSRP, sale price, bulk discount tiers
- Promotion and coupon code management
- Product search and filtering
- Category taxonomy management
- Supplier-to-SKU cost-basis linkage (for COGS)

---

### `order_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8003  
**Database:** PostgreSQL (orders, line items, status history)  
**Cache:** Redis (order status lookups)  
**Purpose:** Order lifecycle management from placement through completion.

- Order creation (validates inventory, calculates tax, charges payment)
- Order state machine: `pending → confirmed → in_fulfillment → shipped → delivered → closed`
- Cancellation and modification handling
- Return and refund initiation
- Order event publishing (triggers downstream fulfillment, accounting, notifications)
- B2C and wholesale order types

---

### `inventory_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8004  
**Database:** PostgreSQL (stock levels per SKU per fulfillment center, reservation records, movement history)  
**Cache:** Redis (real-time available stock counters)  
**Purpose:** Real-time inventory tracking and allocation.

- Stock level queries (available, reserved, on-hand)
- Inventory reservation and release during order lifecycle
- Stock adjustment (receive from supplier, damage write-offs, cycle count corrections)
- Reorder point monitoring and low-stock alert publishing
- Multi-location inventory allocation logic (which fulfillment center fulfills which order)
- Purchase order receipt processing (books incoming stock)

---

### `fulfillment_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8005  
**Database:** PostgreSQL (fulfillment jobs, pick lists, packing records)  
**Cache:** Redis (job queue, worker assignment)  
**Purpose:** Manages the physical fulfillment workflow inside warehouses.

- Receives fulfillment jobs from order_service
- Generates pick lists for warehouse workers
- Tracks pick → pack → ready-to-ship status
- Interfaces with shipping_service to request labels
- Records actual items packed vs. ordered (catches discrepancies)
- Fulfillment center capacity and workload balancing
- Worker productivity metrics per fulfillment center

---

### `shipping_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8006  
**Database:** PostgreSQL (shipments, tracking events, carrier invoices)  
**Purpose:** Carrier integration for rate shopping, label generation, and tracking.

- Rate shopping across fictional carriers (Ground, Express, Overnight)
- Shipping label generation (returns fictional tracking numbers)
- Tracking event ingestion and status updates
- Carrier invoice reconciliation (billed weight vs. quoted weight)
- Shipment exception handling (lost, damaged, delayed)
- Returns label generation

---

### `payment_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8007  
**Database:** PostgreSQL (transactions, payment methods, refunds, disputes)  
**Purpose:** Payment capture, refund, and reconciliation.

- Payment authorization and capture (mock processor)
- Refund processing
- Chargeback/dispute tracking
- Payment method tokenization storage
- Daily settlement reconciliation (simulated processor batch files)
- Failed payment retry logic

---

### `tax_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8008  
**Database:** PostgreSQL (tax rates by jurisdiction, collected tax ledger, filing records)  
**Purpose:** Sales tax calculation, collection tracking, and remittance reconciliation.

- Real-time tax rate lookup by product category × shipping destination jurisdiction
- Tax calculation on order checkout
- Collected tax ledger (what was collected per order per jurisdiction)
- Periodic tax liability summary reports (by filing period per jurisdiction)
- Tax remittance recording (marks tax as filed/paid)
- Tax reconciliation: collected vs. remitted vs. due
- Nexus configuration (which jurisdictions GLC has tax obligations in)

---

### `supplier_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8009  
**Database:** PostgreSQL (suppliers, contracts, purchase orders, invoices, receipts)  
**Purpose:** Supplier relationship and procurement management.

- Supplier directory (contact info, payment terms, lead times, reliability ratings)
- Purchase order creation, approval workflow, and issuance
- PO acknowledgement and confirmation tracking
- Supplier invoice receipt and three-way match (PO → receipt → invoice)
- Accounts payable aging (what GLC owes suppliers and when it's due)
- Supplier performance scoring (on-time delivery rate, fill rate, invoice accuracy)
- Contract and pricing agreement management

---

### `accounting_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8010  
**Database:** PostgreSQL (chart of accounts, journal entries, general ledger, periods)  
**Purpose:** Double-entry bookkeeping and financial reporting.

- Chart of accounts (assets, liabilities, equity, revenue, expenses)
- Journal entry creation (double-entry)
- General ledger maintenance
- Automated entries triggered by business events (order revenue, COGS, AP, AR, tax, payroll)
- Accounts receivable aging
- Accounts payable aging
- Period-end close process (lock period, run reconciliations)
- Financial statements: Income Statement, Balance Sheet, Cash Flow Statement
- Intercompany allocation (allocating shared costs across departments)

---

### `hr_payroll_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8011  
**Database:** PostgreSQL (employees, departments, roles, compensation, payroll runs, pay stubs, time records)  
**Purpose:** Human resources and payroll processing.

- Employee directory (name, role, department, hire date, employment type)
- Compensation management (salary, hourly rate, bonus structure)
- Departmental org chart
- Biweekly payroll run processing:
  - Gross pay calculation
  - Tax withholding (federal income tax, state income tax, FICA)
  - Benefit deductions (health, 401k, dental)
  - Net pay calculation
  - Payroll journal entry posted to accounting_service
- Pay stub generation
- PTO accrual and balance tracking
- Headcount and labor cost reporting

---

### `notification_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8012  
**Database:** MongoDB (notification log, templates, delivery status)  
**Cache:** Redis (pub/sub subscriber)  
**Purpose:** Centralized outbound communication hub.

- Listens to Redis pub/sub channels for business events
- Email notifications (order confirmation, shipping updates, password reset, invoices)
- Internal alerts (low stock, failed payments, overdue supplier invoices, payroll complete)
- Notification templates per event type
- Delivery log and retry tracking
- Digest/batching support (e.g., daily inventory summary to warehouse manager)

---

### `reporting_service`
**Type:** FastAPI + Uvicorn  
**Port:** 8013  
**Database:** MongoDB (pre-computed report snapshots) + reads from PostgreSQL  
**Cache:** Redis (cached report results)  
**Purpose:** Aggregated business intelligence and operational reporting.

- Sales reports (daily, weekly, monthly, by product, by region)
- Inventory turnover and aging reports
- Fulfillment performance (fill rate, pick accuracy, cycle time)
- Shipping cost analysis
- Customer cohort analysis (repeat purchase rate, LTV)
- Supplier performance dashboards
- Financial KPIs (gross margin, operating expenses, burn rate)
- Payroll cost by department over time
- Report scheduling and snapshot storage

---

### `customer_simulator`
**Type:** Python standalone service (asyncio loop)  
**Purpose:** Drives synthetic customer activity to create realistic business volume.

- Generates customer registrations at a configurable rate
- Browses products, adds to cart, completes purchases (or abandons)
- Submits support tickets, initiates returns
- Configurable load profiles: steady, ramp-up, spike, day/night patterns
- Seeds realistic names, addresses, and email addresses
- Configurable order value distribution (small, medium, large, bulk)
- Publishes activity metrics to Redis for monitoring

---

### `supplier_simulator`
**Type:** Python standalone service (asyncio loop)  
**Purpose:** Models supplier behavior in response to purchase orders.

- Polls supplier_service for open/pending purchase orders
- Responds with order acknowledgements and confirmations
- Simulates inventory shipment with configurable lead times
- Occasionally generates: partial shipments, backorders, wrong-quantity receipts, late deliveries
- Generates supplier invoices (sometimes with discrepancies for reconciliation practice)
- Configurable reliability profiles per fictional supplier

---

## Data Architecture

### PostgreSQL — Transactional / Relational Data

Used for all data requiring ACID transactions, relational integrity, and financial auditability.

| Schema / Database       | Owned By               | Key Tables                                                                |
|-------------------------|------------------------|---------------------------------------------------------------------------|
| `customers`             | customer_service       | customers, addresses, payment_methods, support_tickets                    |
| `orders`                | order_service          | orders, order_line_items, order_events                                    |
| `inventory`             | inventory_service      | sku_stock, reservations, stock_movements, fulfillment_centers             |
| `fulfillment`           | fulfillment_service    | fulfillment_jobs, pick_lists, pack_records                                |
| `shipping`              | shipping_service       | shipments, tracking_events, carrier_invoices                              |
| `payments`              | payment_service        | transactions, refunds, disputes, settlements                              |
| `tax`                   | tax_service            | tax_rates, tax_collected_ledger, tax_filing_periods, remittances          |
| `suppliers`             | supplier_service       | suppliers, purchase_orders, po_line_items, supplier_invoices, receipts    |
| `accounting`            | accounting_service     | accounts, journal_entries, ledger_lines, periods                          |
| `hr_payroll`            | hr_payroll_service     | employees, departments, compensation, payroll_runs, pay_stubs, pto        |
| `products_pricing`      | product_service        | pricing, promotions, coupon_codes                                         |

Each service owns its own PostgreSQL schema and manages its own migrations. Services do not query each other's schemas directly. They call the owning service's API.

### MongoDB — Document / Catalog / Log Data

Used for flexible-schema data, high-write event logs, and content management.

| Collection Group        | Owned By               | Key Collections                                                          |
|-------------------------|------------------------|--------------------------------------------------------------------------|
| `product_catalog`       | product_service        | products, variants, categories, images                                   |
| `customer_profiles`     | customer_service       | activity_logs, preferences, ticket_messages                              |
| `notifications`         | notification_service   | notification_log, templates                                              |
| `reporting`             | reporting_service      | report_snapshots, scheduled_reports                                      |
| `system_events`         | shared                 | audit_log, service_health_events                                         |

### Redis — Cache, Sessions, Queues, Pub/Sub

| Usage Pattern           | Details                                                                   |
|-------------------------|---------------------------------------------------------------------------|
| Session Store           | Website user sessions (TTL-keyed by session token)                        |
| API Cache               | Product pages, order status lookups, report results (short TTL)           |
| Inventory Counters      | Real-time available stock per SKU (fast atomic decrement on reservation)  |
| Rate Limiting           | API Gateway per-IP and per-user rate limit counters                       |
| Job Queues              | Fulfillment job queue, notification dispatch queue (Redis Lists)          |
| Pub/Sub Channels        | Business event bus: `orders.*`, `inventory.*`, `payments.*`, etc.         |
| Distributed Locks       | Payroll run lock, period-close lock, inventory adjustment lock            |

---

## Infrastructure & Tooling

### Docker Compose Services

| Service Name             | Image / Build         | Purpose                                      |
|--------------------------|-----------------------|----------------------------------------------|
| `postgres`               | `postgres:16`         | Primary relational database                  |
| `mongo`                  | `mongo:7`             | Document database                            |
| `redis`                  | `redis:7-alpine`      | Cache, queues, pub/sub                       |
| `adminer`                | `adminer`             | PostgreSQL web UI (dev/debug)                |
| `mongo-express`          | `mongo-express`       | MongoDB web UI (dev/debug)                   |
| `redis-commander`        | `rediscommander`      | Redis web UI (dev/debug)                     |
| All microservices        | Local Dockerfile      | One container per service                    |

### Networking

All services share a single Docker bridge network (`glc_network`). Services communicate by container name as hostname (e.g., `http://order_service:8003`). The only externally exposed ports are the website (8000), the API gateway (8080), and the database admin UIs (dev only).

### Health Checks

Every FastAPI service exposes a `GET /health` endpoint returning service name, version, uptime, and dependency status. Docker Compose uses these for container health checks and startup ordering.

### Database Migrations

PostgreSQL schemas are managed with **Alembic**. Each service has its own `alembic/` directory and runs migrations at startup. MongoDB collections are initialized with seed scripts.

### Configuration

All configuration is via environment variables, loaded through **pydantic-settings** `BaseSettings` in each service. A root `.env` file (not committed) holds secrets; `docker-compose.yml` distributes them to the appropriate containers.

---

## Directory Structure

```
general_logistics_co/
│
├── docker-compose.yml              # Full system orchestration
├── docker-compose.dev.yml          # Dev overrides (volume mounts, debug ports)
├── .env.example                    # Template for environment variables
├── README.md                       # This file
│
├── shared/                         # Shared Python library (internal package)
│   ├── glc_shared/
│   │   ├── models/                 # Shared Pydantic models / schemas
│   │   ├── events/                 # Redis pub/sub event definitions
│   │   ├── db/                     # DB connection helpers
│   │   └── utils/                  # Common utilities (logging, tracing, etc.)
│   └── pyproject.toml
│
├── website/                        # Customer-facing storefront + admin UI
├── api_gateway/                    # API Gateway / ingress
├── customer_service/               # Customer CRM
├── product_service/                # Product catalog
├── order_service/                  # Order lifecycle
├── inventory_service/              # Inventory management
├── fulfillment_service/            # Warehouse fulfillment
├── shipping_service/               # Carrier / shipping
├── payment_service/                # Payment processing
├── tax_service/                    # Sales tax
├── supplier_service/               # Supplier / procurement
├── accounting_service/             # General ledger / financials
├── hr_payroll_service/             # HR and payroll
├── notification_service/           # Outbound notifications
├── reporting_service/              # BI and reporting
├── customer_simulator/             # Synthetic customer traffic
└── supplier_simulator/             # Synthetic supplier behavior
```

### Per-Service Layout (FastAPI services)

```
<service_name>/
├── Dockerfile
├── pyproject.toml                  # Dependencies (pip / uv)
├── .env.example
├── app/
│   ├── main.py                     # FastAPI app entrypoint
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── routes/                     # API route handlers
│   ├── models/                     # SQLAlchemy / Pydantic models
│   ├── services/                   # Business logic layer
│   ├── repositories/               # DB access layer
│   └── events/                     # Pub/sub publishers/subscribers
└── alembic/                        # DB migration scripts (PostgreSQL services)
```

### Website Layout

```
website/
├── Dockerfile
├── pyproject.toml
├── app/
│   ├── main.py
│   ├── config.py
│   ├── routes/
│   ├── templates/                  # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── storefront/
│   │   └── admin/
│   └── static/
│       ├── css/
│       │   └── tailwind.css        # Compiled TailwindCSS output
│       └── js/
└── tailwind.config.js
```

---

## Technology Stack

| Layer                   | Technology                                     |
|-------------------------|------------------------------------------------|
| Language                | Python 3.12+                                   |
| REST API Framework      | FastAPI + Uvicorn                              |
| Web UI                  | FastAPI + Jinja2 templates + TailwindCSS       |
| Relational DB           | PostgreSQL 16                                  |
| Document DB             | MongoDB 7                                      |
| Cache / Queue / Pub-Sub | Redis 7                                        |
| ORM                     | SQLAlchemy 2.x (async)                         |
| DB Migrations           | Alembic                                        |
| MongoDB Driver          | Motor (async)                                  |
| Redis Client            | redis-py (async)                               |
| Settings / Config       | pydantic-settings                              |
| Data Validation         | Pydantic v2                                    |
| HTTP Client             | httpx (async)                                  |
| Containerization        | Docker + Docker Compose                        |
| CSS Framework           | TailwindCSS (CDN or compiled)                  |
| Package Management      | uv (fast Python package manager)               |

---

## Key Business Operations (AI Automation Targets)

The following operations are intentionally designed to be manual, repetitive, and time-consuming — representing the highest-value targets for future AI + automation demonstration. Each includes an estimated employee time cost for baseline ROI calculation.

### Finance & Accounting

| Operation | Description | Est. Manual Time |
|-----------|-------------|-----------------|
| **Supplier Invoice 3-Way Match** | Matching supplier invoices to POs and receipts, resolving discrepancies | 2–4 hrs/day |
| **Sales Tax Reconciliation** | Comparing collected tax vs. liability by jurisdiction per filing period | 3–6 hrs/quarter |
| **Month-End Close** | Reconciling all ledger entries, preparing financial statements, locking the period | 1–2 days/month |
| **Carrier Invoice Reconciliation** | Matching carrier billed charges to quoted shipping rates per shipment | 1–2 hrs/day |
| **Accounts Payable Aging Review** | Reviewing overdue supplier balances, prioritizing payments, sending reminders | 1 hr/day |
| **Expense Categorization** | Coding miscellaneous transactions to the correct GL accounts | 1 hr/day |

### Procurement & Inventory

| Operation | Description | Est. Manual Time |
|-----------|-------------|-----------------|
| **Reorder Point Monitoring** | Checking inventory levels, identifying items below reorder threshold | 1–2 hrs/day |
| **Purchase Order Creation** | Drafting POs to suppliers when stock is low, emailing them out | 1–2 hrs/day |
| **Receiving Discrepancy Resolution** | Comparing received quantities to PO, contacting suppliers about shortfalls | 1 hr/day |
| **Inventory Cycle Count Reconciliation** | Reconciling physical counts to system records, posting adjustments | 2–4 hrs/week |
| **Supplier Performance Review** | Pulling on-time delivery rates, fill rates, invoice accuracy per supplier | 2 hrs/month |

### Operations & Fulfillment

| Operation | Description | Est. Manual Time |
|-----------|-------------|-----------------|
| **Order Exception Handling** | Reviewing orders stuck in error states, manually intervening | 1–2 hrs/day |
| **Shipment Exception Triage** | Reviewing lost/damaged/delayed shipments, initiating claims or reshipping | 1–2 hrs/day |
| **Return Processing** | Manually reviewing return requests, approving, restocking inventory | 1 hr/day |
| **Fulfillment Workload Balancing** | Determining which fulfillment center handles which orders each morning | 30 min/day |

### Customer Support

| Operation | Description | Est. Manual Time |
|-----------|-------------|-----------------|
| **Support Ticket Routing** | Reading tickets, assigning to correct team/agent | 1–2 hrs/day |
| **Order Status Inquiry Responses** | Responding to "where is my order" customer emails | 2–3 hrs/day |
| **Refund & Dispute Resolution** | Reviewing cases, making approval decisions, processing | 1–2 hrs/day |
| **Customer Escalation Summaries** | Preparing case summaries for manager review | 30 min/day |

### HR & Payroll

| Operation | Description | Est. Manual Time |
|-----------|-------------|-----------------|
| **Payroll Audit** | Reviewing payroll run output for anomalies before approving | 2–3 hrs/payroll cycle |
| **PTO Balance Reporting** | Pulling PTO balances for employees who request them | 30 min/day |
| **Headcount & Labor Cost Reports** | Compiling department headcount and labor cost summaries for management | 1–2 hrs/week |
| **New Employee Onboarding Setup** | Creating accounts, assigning roles, configuring access | 1 hr/employee |

### Reporting & Analytics

| Operation | Description | Est. Manual Time |
|-----------|-------------|-----------------|
| **Daily Sales Report** | Compiling prior day's sales, units sold, top SKUs into a management summary | 30–60 min/day |
| **Weekly Inventory Report** | Compiling current stock levels, slow movers, stockout risks | 1–2 hrs/week |
| **Monthly P&L Narrative** | Writing the narrative explanation accompanying the monthly P&L | 2–4 hrs/month |
| **Ad-hoc Data Pulls** | Responding to manager requests for custom data extracts | 1–3 hrs/request |

---

## Getting Started

### Prerequisites

- Docker Engine 24+
- Docker Compose v2
- (Optional, for local dev) Python 3.12+, `uv`

### Quick Start

```bash
# Clone and enter the project
cd general_logistics_co

# Copy environment template
cp .env.example .env
# Edit .env with any desired overrides

# Start all services
docker compose up --build

# The following will be available:
#   Website storefront:     http://localhost:8000
#   API Gateway:            http://localhost:8080
#   Adminer (PostgreSQL):   http://localhost:8081
#   Mongo Express:          http://localhost:8082
#   Redis Commander:        http://localhost:8083
```

### Starting Individual Services (Development)

```bash
# Start only infrastructure
docker compose up postgres mongo redis

# Run a specific service locally
cd order_service
uv run uvicorn app.main:app --reload --port 8003
```

### Seeding Data

```bash
# After all services are running, seed reference data:
docker compose exec customer_simulator python seed.py

# This will:
#   - Create the product catalog
#   - Create fictional suppliers
#   - Set up fulfillment centers
#   - Create initial employee roster
#   - Set opening inventory balances
```

### Running Simulators

```bash
# Start customer traffic (defaults to ~20 orders/hour)
docker compose up customer_simulator

# Start supplier simulation
docker compose up supplier_simulator
```

---

## Environment Variables

All secrets and configuration are managed via environment variables. See `.env.example` for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `POSTGRES_HOST` | PostgreSQL hostname |
| `POSTGRES_PORT` | PostgreSQL port (default: 5432) |
| `POSTGRES_USER` | PostgreSQL superuser |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `MONGO_URI` | MongoDB connection URI |
| `REDIS_URL` | Redis connection URL |
| `JWT_SECRET_KEY` | Secret key for JWT token signing |
| `SIMULATOR_ORDERS_PER_HOUR` | Target order rate for customer_simulator |
| `SIMULATOR_VARIANCE_PCT` | Order rate variance percentage |
| `LOG_LEVEL` | Global log level (DEBUG, INFO, WARNING) |

Each service additionally has its own service-specific variables documented in its local `.env.example`.

---

## Development Guide

### Code Style

- All Python code formatted with **black** and linted with **ruff**
- Type hints required on all function signatures
- Pydantic models for all request/response schemas
- SQLAlchemy models for all PostgreSQL tables
- Async-first: all route handlers, DB queries, and external calls must be `async`

### Adding a New Service

1. Create a new directory at the project root matching the service name
2. Copy the service scaffold from an existing simple service
3. Add the service to `docker-compose.yml`
4. Register routes in `api_gateway` if externally accessible
5. Define any pub/sub events the service publishes/subscribes to in `shared/glc_shared/events/`

### Logging and Tracing

All services use structured JSON logging via Python's standard `logging` module configured with a JSON formatter. Every request is tagged with a `correlation_id` (injected by the API gateway, propagated via HTTP headers) to enable end-to-end request tracing across services.

### Testing

Each service includes:
- Unit tests for service/business logic layer (`tests/unit/`)
- Integration tests against a real test database (`tests/integration/`)
- A `docker-compose.test.yml` for spinning up isolated test infrastructure

```bash
# Run tests for a specific service
cd order_service
uv run pytest tests/ -v
```