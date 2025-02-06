# app.py
from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
import utils 
# Import utility functions
import logging  # Import logging module
import vertexai
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
from google.api_core.exceptions import InvalidArgument  # Import the correct exception

app = Flask(__name__)

load_dotenv()  # Load environment variables from .env file
logging.basicConfig(level=logging.INFO)  # Set up logging
logging.info(f"GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")

# Load the model and environment variables
PROJECT_ID = os.getenv('PROJECT_ID')
LOCATION = os.getenv('LOCATION')
MODEL_NAME = os.getenv('MODEL_NAME')  # Load from .env

# Check for required environment variables
if not all([PROJECT_ID, LOCATION, MODEL_NAME]):
    logging.error("Missing required environment variables.")
    raise EnvironmentError("Required environment variables are not set.")

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Load the fine-tuned model
model = GenerativeModel(MODEL_NAME)

UPLOAD_FOLDER = 'uploads'  # Consider a more robust location (e.g., outside the app directory)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            logging.info("Form submitted!")
            logging.info("Form data: %s", request.form)
            logging.info("Files: %s", request.files)

            # Validate analysis name
            analysis_name = request.form.get("analysis_name", "").strip()
            blueprint_file = request.files.get("blueprint")

            logging.info("Blueprint file received: %s", blueprint_file.filename if blueprint_file else "No file received")

            additional_data = {
                "persona": request.files.get("persona"),
                "kpis": request.files.get("kpis"),
                "stakeholder_maps": request.files.get("stakeholder_maps"),
                "system_map": request.files.get("system_map"),
                "user_journey_map": request.files.get("user_journey_map"),
                "project_roadmap": request.files.get("project_roadmap"),
            }

            # Validate required files
            if not blueprint_file:
                return render_template("index.html", error="Blueprint file is required")

            prompt = utils.construct_prompt(analysis_name, blueprint_file, additional_data, app.config['UPLOAD_FOLDER'])
            logging.info("Generated Prompt: %s", prompt)

            try:
                response = model.generate_content(
                    contents=prompt,
                    generation_config={
                        "max_output_tokens": 2048,
                        "temperature": 0.7,
                        "top_p": 0.8,
                    }
                )

                logging.info("Full Model Response: %s", response.text)

                # Default fallback values
                default_swot = {
                    'strengths': ['No strengths identified'],
                    'weaknesses': ['No weaknesses identified'],
                    'opportunities': ['No opportunities identified'],
                    'threats': ['No threats identified']
                }
                default_improvements = ['No improvements suggested']

                if response and hasattr(response, 'text'):
                    try:
                        swot_analysis, improvements = utils.parse_gemini_response(response.text)
                    except Exception as parse_error:
                        logging.error("Parsing Error: %s", parse_error)
                        swot_analysis = default_swot
                        improvements = default_improvements

                    return render_template("results.html",
                        analysis_name=analysis_name,
                        swot=swot_analysis,
                        improvements=improvements)
                else:
                    return render_template("results.html",
                        analysis_name=analysis_name,
                        swot=default_swot,
                        improvements=default_improvements)

            except InvalidArgument as e:
                logging.error("Vertex AI InvalidArgument Error: %s", e)
                return render_template("index.html", error=f"Error processing request (InvalidArgument): {e}")

        except Exception as e:
            logging.error("Full error details: %s", str(e))
            return render_template("index.html", error=f"Detailed Error: {str(e)}")

    return render_template("index.html")

logging.info(f"Project ID: {PROJECT_ID}")
logging.info(f"Location: {LOCATION}")
logging.info(f"Model Name: {MODEL_NAME}")
logging.info(f"Credentials Path: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
if __name__ == "__main__":
    app.run(debug=True)
