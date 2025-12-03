
# **OpsGuardian – AI-Powered Incident Triage and Troubleshooting Assistant**

OpsGuardian is a **full-stack AI-driven incident analysis assistant** built using a **Spring Boot (MySQL) backend**, **Python multi-agent system**, and **Google ADK/Gemini** for intelligent incident classification and troubleshooting suggestions. It automates the earliest and slowest phase of operational workflows: *incident triage*.

OpsGuardian analyzes raw incident descriptions, assigns priority, classifies category, updates ticket status, and generates actionable remediation suggestions. When LLM quotas or network issues occur, the system intelligently falls back to deterministic heuristics to ensure uninterrupted operation.

---

## **Key Features**

* **AI-powered classification** of category and priority
* **Troubleshooting suggestions** generated via ADK/Gemini or heuristics
* **Multi-agent architecture** (reader, classifier, suggester, router)
* **Spring Boot + MySQL backend** with clean REST API
* **Full automation of triage lifecycle**
* **Resilient heuristics fallback** when LLM unavailable
* **End-to-end test suite** included (`e2e_test.py`)
* **Batch-processing agent** (`run_suggester.py`)
* **Production-style design** suitable for real DevOps/SRE teams

---

## **System Story**

Modern operational teams face high volumes of incidents with repetitive triage workload. OpsGuardian automates the first-response stage of incident handling:

* Normalizes ticket text
* Classifies severity (P0–P3)
* Identifies category (Network, Database, Application, etc.)
* Updates backend status
* Generates structured troubleshooting steps

This reduces triage time from minutes to seconds and ensures consistent, reliable classification even under load or quota limitations.

---

## **Architecture Overview**

### **Backend (Spring Boot + MySQL)**

* REST endpoints under `/api/tickets`
* Stores **tickets** and **suggestions**
* Default ticket status: **OPEN**
* After agent processing: **TRIAGED** or **ASSIGNED**
* Schema includes: *id, title, description, reporter, priority, category, status, createdAt, suggestions*

### **Python Agent System**

* **reader_agent.py** — text normalization
* **adk_classifier.py** — priority + category (ADK or heuristic)
* **adk_suggester.py** — troubleshooting suggestions
* **router_agent.py** — orchestrates complete workflow
* **run_suggester.py** — batch processor
* **backend_client.py** — REST client
* **e2e_test.py** — end-to-end smoke test

### **ADK/Gemini Intelligence**

* LLM-based reasoning for classification + suggestions
* On failure (429 quota), deterministic fallback ensures uninterrupted processing

---

## **Workflow Overview**

```
Ticket → Stored in MySQL (status=OPEN)
Agent → Reads → Normalizes
Agent → Classifies (ADK or heuristic)
Agent → Updates Ticket Status (TRIAGED / ASSIGNED)
Agent → Generates Suggestions
Agent → Stores Suggestions Back to Backend
Engineer → Reviews and Acts
```

---

# **Installation & Setup**

## **Prerequisites**

* Java 17+
* Maven
* Python 3.10+
* MySQL Server
* Google ADK/Gemini API access (optional but recommended)

---

# **1. Backend Setup (Spring Boot + MySQL)**

## **Clone Repository**

```bash
git clone <your-repo-url>
cd OpsGuardian
```

## **Configure MySQL**

In `src/main/resources/application.yml`:

```
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/opsguardian
    username: <your-user>
    password: <your-password>
```

Ensure MySQL database exists:

```sql
CREATE DATABASE opsguardian;
```

## **Run Backend**

```bash
./mvnw spring-boot:run
```

Backend runs at:

```
http://localhost:8080/api
```

---

# **2. Python Agent Setup**

```bash
cd opsguardian-agent
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## **Environment Variables**

Create `.env`:

```
OPS_BACKEND_URL=http://localhost:8080/api
PROCESS_OPEN_ONLY=true
GOOGLE_API_KEY=<your-key>
```

`PROCESS_OPEN_ONLY`:

* `true` → only process OPEN tickets
* `false` → reprocess ALL tickets (useful after schema changes)

---

# **Running the Agent**

## **Process Tickets**

```bash
python run_suggester.py
```

This will:

* Fetch OPEN tickets
* Normalize
* Classify
* Update backend
* Generate suggestions
* Store suggestions

---

# **3. End-to-End Testing**

Run:

```bash
python e2e_test.py
```

This script will:

* Create a new ticket
* Wait for agent to process it
* Verify updated fields + suggestions

If the agent is not running while executing the test, start it separately using:

```bash
python run_suggester.py
```

---

# **API Endpoints**

## **Tickets**

* `POST /api/tickets`
* `GET /api/tickets`
* `GET /api/tickets/{id}`
* `PUT /api/tickets/{id}`
* `POST /api/tickets/{id}/suggestions`
* `POST /api/tickets/{id}/assign`

### **Example Ticket Creation**

```bash
curl -X POST http://localhost:8080/api/tickets \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Checkout Timeout\",\"description\":\"Users facing delays\",\"reporter\":\"ops@example.com\"}"
```

---

# **Folder Structure**

```
OpsGuardian/
│
├── opsguardian-agent/
│   ├── agents/
│   │   ├── reader_agent.py
│   │   ├── router_agent.py
│   │   ├── adk_classifier.py
│   │   ├── adk_suggester.py
│   │   ├── adk_utils.py
│   │   └── adk_runtime.py
│   ├── tools/backend_client.py
│   ├── run_suggester.py
│   ├── e2e_test.py
│   └── requirements.txt
│
└── backend/
    ├── src/main/java/... (Spring Boot)
    ├── src/main/resources/application.yml
    └── pom.xml
```

---

# **Observability & Logging**

OpsGuardian includes robust logging:

* ADK calls
* Fallback triggers
* Ticket update details
* Suggestion storage
* Per-ticket and batch run metrics

`run_suggester.py` prints:

* **processed count**
* **fallback usage**
* **average processing time**

---

# **Troubleshooting**

*Suggestions not visible?*

* Ensure agent is running
* Ensure backend is reachable
* Check logs for ADK quota errors
* Toggle `PROCESS_OPEN_ONLY=false` and re-run agent

*Agent failing with ADK errors?*

* Provide a valid `GOOGLE_API_KEY`
* Free tier may hit 429 limits
* Fallback will still classify & suggest

---

# **Future Enhancements**

* Dedicated Suggestion table
* Feedback loops for ranking suggestions
* Vector embeddings for similar-incident search
* Multi-agent parallelization
* UI dashboard for triage review
* Automatic team assignment

---




