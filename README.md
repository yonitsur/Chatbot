# Startup Knowledge Chatbot API

This FastAPI application provides a chatbot interface specialized in answering questions about startups, leveraging Retrieval-Augmented Generation (RAG) with a Qdrant vector database and OpenAI's language models.

## Table of Contents

-   [Features](#features)
-   [Prerequisites](#prerequisites)
-   [Installation and Setup](#installation-and-setup)
    -   [Step 1: Clone the Repository](#step-1-clone-the-repository)
    -   [Step 2: Configure Environment Variables](#step-2-configure-environment-variables)
    -   [Step 3: Setup Options](#step-3-setup-options)
        -   [Option 1: Using Docker Compose (Recommended)](#option-1-using-docker-compose-recommended)
        -   [Option 2: Manual Setup](#option-2-manual-setup)
    -   [Step 4: Access the Application](#access-the-application)
-   [How to Use the API](#how-to-use-the-api)
    -   [1. Sending a Query (`/query`)](#1-sending-a-query-query)
    -   [2. Summarizing Conversation (`/summarize`)](#2-summarizing-conversation-summarize)
    -   [3. Listing User Sessions (`/sessions/{user_id}`)](#3-listing-user-sessions-sessionsuser_id)
    -   [4. Getting Session History (`/history/{user_id}/{session_id}`)](#4-getting-session-history-historyuser_idsession_id)
    -   [5. Health Check (`/health`)](#5-health-check-health)
    -   [6. Clearing the Database (Testing Only) (`/clear_db_testing_only`)](#6-clearing-the-database-testing-only-clear_db_testing_only)
-   [Configuration (config.py & .env)](#configuration-configpy--env)
-   [Testing](#testing)
-   [UI React App (TBD)](#ui-react-app)
-   [Technical Deep Dive: LLM and RAG Logic](#technical-deep-dive-llm-and-rag-logic)


## Features

* **Conversational Q&A:** Answers user questions about startups.
* **RAG Integration:** Uses a Qdrant vector database containing startup information to ground responses in factual data, reducing hallucination.
* **Context-Awareness:** Maintains conversation history per user/session to understand follow-up questions.
* **Query Rewriting:** Rewrites user queries using conversation history to improve RAG retrieval accuracy for follow-up questions.
* **Domain Control:** Employs an LLM-based classifier to ensure the conversation stays focused on startups and venture capital topics.
* **Summarization:** Provides an endpoint to summarize the recent conversation history.
* **Session Management:** Enables users to manage and retrieve past conversation sessions.
* **Detailed History Retrieval:** Allows retrieval of message history for specific sessions.
* **Asynchronous Processing:** Built with FastAPI and asyncio for efficient handling of requests.
* **Message Skipping:** Handles rapid consecutive user messages gracefully by skipping processing for older, outdated queries.
* **Configurable:** Settings managed via environment variables (`.env` file).
* **Database Storage:** Persists conversation history in a SQLite database (configurable).
* **UI Integration:** TBD

## Prerequisites

* Ensure [Docker](https://docs.docker.com/get-docker/) is installed and running (if using Docker Compose).
* Ensure [Python 3.10+](https://www.python.org/downloads/) is installed (if using manual setup).
* An [OpenAI API Key](https://platform.openai.com/api-keys).

## Installation and Setup

### step 1:
####  Clone the Repository:
```bash
git clone https://github.com/yonitsur/startups-assignment-il-main.git
cd startups-assignment-il-main
```
### step 2:
#### Configure Environment Variables:
1. Copy the sample environment file:
    ```bash
    cp sample.env .env
    ```
2.  Open the newly created `.env` file and **replace `OPENAI_KEY`** with your actual OpenAI API key.
* Review other variables (like `DATABASE_URL`, `QDRANT_URL`, model names, etc.) and adjust if necessary. Defaults are provided in `config.py`.


### step 3:  
### *Option 1*: Using Docker Compose (Recommended)

1.  **Build and Run the Docker Containers (in the background):**
    * Ensure you have Docker and Docker Compose installed.
    * From the project's root folder, run:
    ```bash
    docker compose up -d
    ```
    *(This will build the FastAPI application and Qdrant containers.)*


2. Run Qdrant Initialization Script (needed only once):
    ```bash
    docker exec chatbot-app python -m scripts.init_collection
    ```
    *(This will create the 'startups' collection and upload the initial data vectors.)*


### *Option 2*: Manual Setup


1.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    
3. **Qdrant Vector Database Setup**

The chatbot uses Qdrant to store and search startup data for the RAG system.

**Run Qdrant using Docker:**
* Ensure the `scripts` directory contains `startups_demo.json` and `startup_vectors.npy`.
* From the project's root folder, run:
```bash
docker run -p 6333:6333 -p 6334:6334 \
   -v "$(pwd)/qdrant":/qdrant/storage:z \
   qdrant/qdrant
```

**Initialize Qdrant Collection (needed only once):**
* Run the provided script to create the 'startups' collection and upload the initial data vectors (ensure you are in your virtual environment if you created one):
```bash
python -m scripts.init_collection
```

4. **Running the Service**

**Start the FastAPI Application:**
* Ensure Qdrant is running and your `.env` file is configured.
* Make sure you are in your virtual environment.
* Run the main application script:
```bash
python main.py
```

### step 4:  
### Access the Application

* The FastAPI application will be available at `http://localhost:8000`.
* The React UI will be available at http://localhost:3000.
* Once running, interactive API documentation (Swagger UI) is available at [http://localhost:8000/docs](http://localhost:8000/docs).
* ReDoc documentation is available at [http://localhost:8000/redoc](http://localhost:8000/redoc).
* You can view the Qdrant collection and data via the web UI at [http://localhost:6333/dashboard](http://localhost:6333/dashboard).

## How to Use the API

You can interact with the API using tools like `curl`, Postman, or programmatically.

### 1. Sending a Query (`/query`)

This is the main endpoint to chat with the bot.

**Method:** `POST`
**Endpoint:** `/query`
**Request Body (JSON):**

```json
{
  "message": "Your question about startups here",
  "user_id": "optional_user_identifier",
  "session_id": "optional_session_identifier"
}
```
#### Example Usage with `curl`:
```bash
curl -X 'POST' \
  'http://localhost:8000/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "message": "Are there any interesting AI startups in London?",
  "user_id": "vc_analyst_01",
  "session_id": "london_ai_research_20250414"
}'
```
In PowerShell you can use:
```bash
(Invoke-WebRequest -Uri "http://localhost:8000/query" -Method POST -Headers @{ "Content-Type" = "application/json" } -Body '{"message": "Are there any interesting AI startups in London?"}').content
```

**Response (JSON):**
 * 200 OK
```json
{
  "output": "Based on the available data, here are some AI startups in London...",
  "session_id": "london_ai_research_20250414",
  "message_id": 123
}
```
* 202 Skipped
```json
{
"output": "This message was skipped because a newer message was received.",
"detail": "Message processing skipped because a newer message was received."
}
```
* 500 Internal Server Error/ 503 Service Unavailable

### 2. Summarizing Conversation (`/summarize`)
This endpoint provides a summary of the recent conversation history.

**Method:** `GET`
**Endpoint:** `/summarize`
**Request Body (JSON):**
```json
{
  "user_id": "optional_user_identifier",
  "session_id": "optional_session_identifier"
}
```
#### Example Usage with `curl`:
```bash
curl -X 'GET' \
  'http://localhost:8000/summarize?user_id=vc_analyst_01&session_id=london_ai_research_20250414' \
  -H 'accept: application/json'
```
* **Response (JSON):**


 * 200 OK
```json
{
  "summary": "The user asked about AI startups in London, and the assistant provided information based on the available data, mentioning startups X and Y."
}
```
(Or NO_HISTORY_SUMMARY_MESSAGE if no history is found)

* 500 Internal Server Error


### 3. Listing User Sessions (/sessions/{user_id})
This endpoint retrieves a list of session IDs and their start times for a given user.

**Method:** `GET`
**Endpoint:** `/sessions/{user_id}`
**Path Parameters:**
* `user_id`: The user identifier.
* **Example Usage with `curl`:**
```bash
curl 'http://localhost:8000/sessions/vc_analyst_01'
```

* **Response (JSON):**
 * 200 OK
```json
{
  "sessions": [
    {
      "session_id": "london_ai_research_20250414",
      "start_time": "2024-04-14T12:34:56.789Z"
    },
    {
      "session_id": "another_session_id",
      "start_time": "2024-04-15T10:00:00.000Z"
    }
  ]
}
```

* 500 Internal Server Error

### 4. Getting Session History (`/history/{user_id}/{session_id}`)
This endpoint retrieves the message history for a specific session.
**Method:** `GET`
**Endpoint:** `/history/{user_id}/{session_id}`
**Path Parameters:**
* `user_id`: The user identifier.
* `session_id`: The session identifier.
* **Example Usage with `curl`:**
```bash
curl 'http://localhost:8000/history/vc_analyst_01/london_ai_research_20250414'
```
* response (JSON):
 * 200 OK
```json
{
  "history": [
    {
      "message_id": 123,
      "user_message": "Are there any interesting AI startups in London?",
      "bot_response": "Based on the available data, here are some AI startups in London...",
      "timestamp": "2024-04-14T12:34:56.789Z"
    },
    {
      "message_id": 124,
      "user_message": "What about funding rounds?",
      "bot_response": "The latest funding round for startup X was $5 million.",
      "timestamp": "2024-04-14T12:35:00.000Z"
    }
  ]
}
```

* 500 Internal Server Error

### 5. Health Check (`/health`)
This endpoint checks the health of the application.
**Method:** `GET`
**Endpoint:** `/health`

* **Example Usage with `curl`:**
```bash
curl 'http://localhost:8000/health'
```
* **Response (JSON):**
 * 200 OK
```json
{
  "status": "ok"
}
```


### 6. Clearing the Database (Testing Only) (`/clear_db_testing_only`)
This endpoint clears the conversation database. **Use with caution!**
**Method:** `POST`
**Endpoint:** `/clear_db_testing_only`
** Query Parameters:**
* `user_id` (optional): The user identifier.
* `session_id` (optional): The session identifier.
* `clear_all` (optional): If set to `true`, clears all conversations. Otherwise, clears only the specified user/session.
* **Example Usage with `curl`:**
```bash
curl -X 'POST' \
    'http://localhost:8000/clear_db_testing_only?user_id=vc_analyst_01&session_id=london_ai_research_20250414&clear_all=true' \
    -H 'accept: application/json'
```
* **Response (JSON):**
 * 200 OK
```json
{
  "message": "Conversation database cleared for session 'test_session' for user 'test_user'."
}
```
* 400 Bad Request
* 500 Internal Server Error



### Configuration (config.py & .env)
Key settings are managed via environment variables, loaded using python-dotenv from a .env file.

* `OPENAI_KEY`: Your API key. Required.
* `CHATBOT_MODEL`, `DOMAIN_CLASSIFIER_MODEL`, etc.: Specify which OpenAI models to use.
* `*_TEMPERATURE`, `*_MAX_TOKENS` : Control LLM generation parameters.
* `HISTORY_LIMIT_*` : Control how much history is used for different contexts.
* `QDRANT_*` : Settings for the vector database connection and search.
* `DATABASE_URL`: Connection string for the conversation database (defaults to SQLite).
* `MESSAGE_STATUS_CHECK_DELAY_SECONDS`: How long the /query endpoint waits before checking if its message was skipped.
* `REJECTION_MESSAGE`, `NO_HISTORY_SUMMARY_MESSAGE`: Customizable chatbot responses.
* `UVICORN_*`: Server host, port, and reload settings.
* `LOG_LEVEL`, `LOG_FORMAT`: Configure application logging.

### Testing
* Unit tests are provided in the `tests` directory.
* Ensure you have pytest and other test dependencies installed.


* Run tests using:
```bash
pytest tests/
```
The tests cover:
* Basic query success and failure (rejection).
* Summarization (empty and with history).
* Context handling and query rewriting logic.
* RAG grounding (checking if responses use retrieved data and avoid hallucination).
* Correct handling of consecutive messages (skipping logic).
* Error handling (OpenAI API errors, internal errors).
* User/session isolation.
* Database clearing endpoint functionality.

## UI React App
 TBD


## Technical Deep Dive: LLM and RAG Logic

This application utilizes several key techniques:

1.  **Request Handling & Message Skipping (`main.py`):**
    * The `/query` endpoint logs incoming user messages (`status=pending`).
    * Crucially, if a new message arrives for the same user/session, any older `pending` messages are marked `skipped` to avoid processing outdated queries. The new message proceeds only if it hasn't been skipped itself.

2.  **Core RAG Pipeline (`chatbot_service.py`):**
    * **Query Rewriting:** An LLM refines the user's query using conversation history to create a better, self-contained query for vector search, adapting to follow-up questions and topic shifts.
    * **Retrieval (RAG - Part 1):** The refined query is embedded (`sentence-transformers`), and relevant startup data is retrieved from the Qdrant vector database (`NeuralSearcher`). This step fetches factual context. [More on RAG](https://www.pinecone.io/learn/retrieval-augmented-generation/).
    * **Domain Classification:** A separate LLM checks if the user's query (considering history and retrieved data) is relevant to startups/VC. Irrelevant queries are rejected politely.
    * **Generation (RAG - Part 2):** A detailed system prompt, including the retrieved Qdrant data (or lack thereof), instructs the main LLM (`Chatbot.search`). The prompt strictly requires the LLM to base its answer *only* on the provided context and history, preventing hallucination.

3.  **Summarization (`/summarize` endpoint):**
    * Uses an LLM (`Chatbot.get_summary`) to concisely summarize the recent conversation history for a given user/session.

4.  **Database & ORM (`conversation_db.py`):**
    * Uses **SQLAlchemy** as an ORM (Object-Relational Mapper) to map the Python `Conversation` class to the `conversation` SQL table.
    * This allows interacting with the database using Python objects (e.g., `db.add(obj)`, `db.query(Conversation)`) instead of raw SQL.
    * Database interactions happen within a **Session** managed by the dependency system.

5.  **Dependencies & Resource Management (`dependencies.py`):**
    * Leverages FastAPI's **Dependency Injection** (`Depends`) to provide resources like database sessions (`get_db_session`) or API clients (`get_openai_client`) to route functions.
    * This promotes code reuse and simplifies testing by allowing dependencies to be easily overridden.
    * The `get_db_session` dependency uses `yield` within a `try...finally` block. This common pattern ensures resources (like the DB session) are set up before the request is handled and reliably cleaned up (e.g., session closed) afterwards, even if errors occur.
    * API clients (`OpenAI`, `NeuralSearcher`) are cached using `@lru_cache` for performance, creating them only once.