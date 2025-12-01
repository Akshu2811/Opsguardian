# **OpsGuardian – AI-Driven Incident Analysis & Suggestion Engine**

OpsGuardian is an intelligent incident triage and suggestion system designed to support SRE, DevOps, and Operations teams.
It automates the lifecycle of incident review, categorization, and resolution suggestion using:

* Spring Boot Backend for ticket management

* Python Agent Layer for intelligent classification and recommendation

* ADK/Gemini LLM for generating high-quality troubleshooting suggestions

* Fallback heuristic engine to ensure reliability even when LLM quota is exceeded

OpsGuardian reduces manual effort, improves first-response quality, and accelerates root-cause identification.


### **Key Features**

#### **✓ Intelligent Ticket Triaging****

Each new ticket is read by the agent, classified into priority (P0–P3) and a category using ADK/Gemini (or fallback rules).

#### **✓ Automated Suggestion Generation**

For each ticket, OpsGuardian generates actionable suggestions such as likely root causes, next steps, and recommended checks.

#### **✓ Status Workflow**

Tickets flow through the system automatically:

OPEN -> TRIAGED (after agent processes)

#### **✓ End-to-End Integration**

* Backend stores ticket & suggestion data

* Agent pulls tickets, classifies, updates, and writes suggestions

* ADK handles core LLM reasoning

* Fallback logic ensures zero downtime for LLM quota errors

#### **✓ 100% Reproducible, Hackathon-Friendly Setup**

Simple commands to run backend, agent, and tests.

## **System Architecture**


1. ### **Backend (opsguardian-backend)**

* Spring Boot

* MySQL

* REST API under /api/tickets

* Entities: Ticket, Suggestion

* Endpoints:

     1. POST /api/tickets
     2. GET /api/tickets
     3. GET /api/tickets/{id}
     4. PUT /api/tickets/{id}
     5. POST /api/tickets/{id}/suggestions

2. ### **Python Agent (opsguardian-agent)**

    Components:

* reader_agent.py – cleans & normalizes ticket text

* adk_classifier.py – ADK-based category & priority classification

* adk_suggester.py – ADK-based suggestion engine + fallback

* router_agent.py – orchestrates classification + updates + suggestion writes

* backend_client.py – REST client for interacting with backend

* run_suggester.py – iterates through all OPEN tickets and triages them

* e2e_test.py – complete end-to-end test

3. ### **ADK/Gemini Integration**

* Uses AdkLlmAgent

* Generates:

  * priority

  * category

  * suggestions (root causes, next steps, investigations)

If Gemini quota is exceeded → fallback heuristic suggestions automatically applied.

## **Data Flow**

Backend creates ticket (status=OPEN)

↓

Python agent (run_suggester.py) fetches OPEN tickets

↓

Reader agent cleans text

↓

ADK classifier categorizes & assigns priority

↓

Backend ticket updated → status = TRIAGED

↓

ADK/Gemini suggestion OR fallback heuristic

↓

Suggestion saved to backend


## **How to Run the Project**

### 1️⃣ **Run MySQL**

Make sure MySQL is running locally and your credentials are set.

### 2️⃣ **Run the Spring Boot Backend**

Navigate to the backend directory and run:

```bash
cd opsguardian-backend
./mvnw spring-boot:run
```

Backend runs at:
👉 http://localhost:8080


### 3️⃣ **Run the Python Agent Layer**

Create virtual environment:

```bash
cd opsguardian-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the agent:

```bash
python run_suggester.py
```
✓ **This will process all OPEN tickets**

✓ **Update priority/category**

✓ **Mark as TRIAGED**

✓ **Insert suggestions**

### **Running End-to-End Test**

Navigate to the agent directory and run:

```bash
cd opsguardian-agent
python e2e_test.py
```

This test:

* **Creates a ticket in backend**

* **Verifies it via GET**

* **Confirms the system is functioning end-to-end**

## **API Endpoints Summary**

```table
| Method | Endpoint                        | Description                |
| ------ | ------------------------------- | -------------------------- |
| POST   | `/api/tickets`                  | Create a new ticket        |
| GET    | `/api/tickets`                  | List all tickets           |
| GET    | `/api/tickets/{id}`             | Fetch ticket by ID         |
| PUT    | `/api/tickets/{id}`             | Update ticket fields       |
| POST   | `/api/tickets/{id}/suggestions` | Add suggestions for ticket |
```

## **Sample Ticket SQL (data.sql)**

```sql
INSERT INTO ticket (title, description, status, reporter, created_at)
VALUES
    ('High CPU usage', 'CPU spikes to 97% during peak hours.', 'OPEN', 'john@company.com', '2025-11-28 10:00:00');

```

## **Why OpsGuardian?**

* **Automates triage work SRE teams spend hours on**

* **Ensures consistent and structured ticket classification**

* **Uses LLM-powered reasoning + fallback logic for reliability**

* **Fully modular: backend, agent, and LLM components are cleanly separated**

* **Perfect for hackathons, demonstrations, and real-world workflow**