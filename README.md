# Chat with your Strava data: Multi-agentic workflow that translates NL to SQL and generate visualizations and responses

![Strava Technical Flow Diagram](./technical_flow_diagram.png)

- This repository consists of multiple integration components and it is NOT designed for you to run as a full application.
- The emphasis is for readers to understand the technical flow and how the Gen AI multi-agent system is implemented and integrated with the other components.
- Feel free to contact me if you would like to use the entire repository as a full application.

# Gen AI Architecture

![Gen AI Architecture](./workflow_graph.png)

# Tech Stack
Frontend: Wordpress, Old School HTML + CSS + JS  
Backend: Python, FastAPI, PostgreSQL (RDMS + Vector Store)  
AI Backend: LangChain, LangGraph, Google Gemini

# Startup Instructions
- For application
`python deploy_v2.py`
- For running Gen AI workflow
`python workflow_debug.py`