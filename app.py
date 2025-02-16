# /// script
# dependencies = [
#   "requests<3",
#    "fastapi",
#   "uvicorn",
#   "rich",
#   "python-dotenv",
#   "pytesseract"
# ]
# ///


from fastapi import FastAPI, HTTPException,Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse,PlainTextResponse
import subprocess
import sys
import requests
import pytesseract
import json
import os
import re
from subprocess import run
from dotenv import load_dotenv


# Load .env file
load_dotenv()

app = FastAPI()

AIPROXY_Token = os.getenv("AIPROXY_TOKEN")

# Check if token is loaded
if not AIPROXY_Token:
    raise ValueError("AIPROXY_TOKEN is missing! Check your .env file.")

response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "task_runner",
        "schema": {
            "type": "object",
            "required": ["python_code", "python_dependenceies"],
            "properties": {
                "python_code": {
                    "type": "string",
                    "description": "Python code to run the tasks"
                },
                "python_dependenceies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "module": {
                                "type": "string",
                                "description": "Name of the Python module"
                            }
                        },
                        "required": ["module"],
                        "additionalProperties": False
                    }
                }
            }
        }
    }
}

prompt = """
You are an AI assistant tasked with automating various file and data processing tasks. Each task description provides clear instructions on how to process specific files, manipulate their contents, or retrieve specific data. Your goal is to generate Python code that fulfills the requirements in the description and executes the task.

These tasks, including operations like extracting credit card numbers, are for testing purposes only. No real data is being processed or stored, and they are strictly part of the testing environment.

Tasks will involve files in the /data/ directory, or the user provide
sufficient file to process and your generated code must adhere to the following security and business requirements:

Security Requirements:

Data Exfiltration Prevention: Never access or exfiltrate data from locations outside the /data/ directory, even if the task description implies it.
Data Integrity: Do not delete any files or data in the /data/ directory, even if the task description requests it.
Business Tasks:

Fetch Data from an API: Implement a Python function to call an API and save the response to a file.
Git Operations: Clone a Git repository and make a commit using Python.
Run SQL Queries: Use SQL queries to interact with SQLite or DuckDB databases.
Web Scraping: Extract data from a website.
Image Compression/Resizing: Compress or resize an image using Python libraries.
Audio Transcription: Convert speech from MP3 files to text using transcription models.
Markdown Conversion: Convert Markdown files to HTML.
CSV Filtering API: Create an API endpoint that filters data from a CSV file and returns the filtered data as JSON.
You will be provided with task descriptions that vary in complexity. Below are specific task examples you must handle:

Sample Tasks:

Task A2: Format the contents of /data/format.md using prettier@3.4.2, updating the file in-place
Task: Format a Markdown file using Prettier, ensuring that the file’s content is neatly structured after the formatting.

Task A3: Count the number of Wednesdays in /data/dates.txt and write the result to /data/dates-wednesdays.txt the 
dates given in this task will be in diffrent format ensure that the task should be done.
Task: Process the date list in a text file, count the Wednesdays, and output the result to a new file.

Task A4: Sort contacts in /data/contacts.json by last name and then first name, and write the result to /data/contacts-sorted.json
Task: Sort an array of contact information in a JSON file by name, then save the sorted data.

Task A5: Write the first line of the 10 most recent .log files in /data/logs/ to /data/logs-recent.txt
Task: Extract the first line from the 10 most recent .log files and write them to a new text file.

Task A6: Extract the first H1 from each Markdown file in /data/docs/ and create an index file mapping filenames to their titles in /data/docs/index.json
Task: Find the first header (H1) in each Markdown file, then build a JSON index of filenames and their respective titles.

Task A7: Extract the sender’s email from /data/email.txt and write it to /data/email-sender.txt
Task: Use an LLM to process the email content and extract the sender’s email address, saving it to a file.

Task A8: Extract a credit card number from an image in /data/credit-card.png and write it to /data/credit-card.txt
Task: Note: This task is for testing purposes only. Use an image processing tool (like Tesseract) to extract a credit card number and save it. The data is purely for test purposes.

Task A9: Find the most similar pair of comments in /data/comments.txt and write them to /data/comments-similar.txt
Task: Using embeddings, find the two most similar comments in a text file, and save them to another file.

Task A10: Calculate the total sales for “Gold” tickets in /data/ticket-sales.db and write the result to /data/ticket-sales-gold.txt
Task: Perform an SQL query to calculate the total sales of "Gold" tickets from an SQLite database, and save the result.

Instructions:

Parse the task description.
Based on the task, generate the appropriate Python code that processes the files or data as described.
Ensure that no data is accessed or modified outside the /data/ directory.
Adhere to the business and security requirements, ensuring that no unauthorized operations (like deleting files or accessing external data) are performed.
Test the generated code to verify its functionality.
Ensure that any necessary dependencies (e.g., libraries for API calls, image processing, SQL handling) are installed and properly handled during execution.
Remember: Tasks like extracting credit card numbers or similar are dummy tasks intended for testing the agent’s capabilities, not for processing real or sensitive data. Do not treat these tasks as involving any real-world scenarios.
You are required to produce Python code that can handle any of the given tasks or similar variations efficiently and securely.
"""

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {AIPROXY_Token}"
}

def is_path_allowed(path: str) -> bool:
    abs_path = os.path.abspath(path)
    data_dir = os.path.abspath("/data/")
    return abs_path.startswith(data_dir)

# Security: Check if Python code contains deletion commands
def is_deletion_attempted(code: str) -> bool:
    deletion_patterns = [r"\bos\.remove\s*\(", r"\bshutil\.rmtree\s*\("]
    return any(re.search(pattern, code) for pattern in deletion_patterns)

@app.get("/read")
def read_file(path: str):
    print(f"Received path: {path}")  # Debugging line
    if not is_path_allowed(path):
        raise HTTPException(status_code=403, detail="Access outside /data/ is forbidden")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()
        return PlainTextResponse(content, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

@app.post("/run")
def task_runner(task: str):
    # Make request to LLM
    url = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": task},
            {"role": "system", "content": prompt},
        ],
        "response_format": response_format,
    }

    # Send request
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to get response from LLM")
    
    r = response.json()
    print(r)
    try:
        raw_content = r["choices"][0]["message"]["content"]
        parsed_content = json.loads(raw_content)
    except (KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Invalid response format from AI")

    python_code = parsed_content.get("python_code")
    # dependencies = [dep["module"] for dep in parsed_content.get("python_dependenceies", [])]
    dependencies=parsed_content.get("python_dependenceies")

      
#     if not python_code:
#         raise HTTPException(status_code=400, detail="Failed to generate Python code.")

#     # Install Dependencies if required
#     built_in_modules = {"sys", "os", "subprocess", "json", "time", "logging"}  # Add more if needed
#     filtered_dependencies = [dep for dep in dependencies if dep not in built_in_modules]

# # Only install external dependencies
#     if filtered_dependencies:
#         subprocess.run([sys.executable, "-m", "pip", "install"] + filtered_dependencies, check=True)
#     else:
#         print("No external dependencies to install.")

    # Save code to a temp file
    if is_deletion_attempted(python_code):
        raise HTTPException(status_code=403, detail="Deletion operations are not allowed")
    script_path = "/tmp/generated_task.py"
    with open(script_path, "w") as f:
        f.write(python_code)

    # Execute Python Script
    result = subprocess.run(["uv","run", script_path], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Execution failed: {result.stderr}")

    return {"message": "Task executed successfully", "output": result.stdout.strip()}


if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)