# AI-Driven Service Blueprint Analyzer

## Overview
The **AI-Driven Service Blueprint Analyzer** is a Flask-based web application designed to analyze service blueprints and generate actionable insights. It leverages AI to automate the process of interpreting blueprint structures, improving efficiency in service design and optimization.

## Features
- **AI-Powered Analysis**: Extracts insights from service blueprint diagrams without requiring manual text extraction.
- **Flask-Based API**: Lightweight, scalable backend built with Flask.
- **Cloud-Based Processing**: Supports integration with APIs like OpenAI, Gemini, and Claude.
- **User-Friendly Interface**: Interactive web application with a clean UI.
- **Integration Support**: Can be integrated into existing workflows with ease.

## Project Structure
```
Project Folder
│── __init__.py
│── app.py
│── .env
│── utils.py
│── requirements.txt
│── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── scripts.js
│── templates/
│   ├── index.html
│   ├── results.html
│── tests/
│   ├── test_app.py
│   ├── test_error_handling.py
│   ├── test_integration.py
│   ├── test_functional.py
│   ├── test_utils.py
```

## Installation
### **Prerequisites**
- Python 3.8+
- Flask
- Virtual Environment (recommended)
- Git

### **Step 1: Clone the Repository**
```sh
git clone https://github.com/Mehredad/AI-DrivenServiceBlueprintAnalyzer.git
cd AI-DrivenServiceBlueprintAnalyzer
```

### **Step 2: Create a Virtual Environment**
```sh
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate  # On Windows
```

### **Step 3: Install Dependencies**
```sh
pip install -r requirements.txt
```

## Usage
### **Running the Application**
```sh
python app.py
```
The application should now be running at `http://127.0.0.1:5000/`.

### **Testing the Application**
To run the test suite:
```sh
pytest tests/
```

## API Endpoints
| Endpoint       | Method | Description |
|---------------|--------|-------------|
| `/`           | GET    | Load homepage |
| `/analyze`    | POST   | Analyze uploaded service blueprint |
| `/results`    | GET    | View analysis results |

## Deployment
To deploy on a cloud platform like **Heroku**, follow these steps:
```sh
git push heroku main
```

Alternatively, for **Docker deployment**:
```sh
docker build -t blueprint-analyzer .
docker run -p 5000:5000 blueprint-analyzer
```

## Contribution Guidelines
1. Fork the repository.
2. Create a new branch: `git checkout -b feature-branch`.
3. Commit changes: `git commit -m "Added new feature"`.
4. Push to the branch: `git push origin feature-branch`.
5. Submit a pull request.

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for details. Reference to the project 
You are free to use, modify, and distribute it for any purpose, provided you include proper attribution. Please reference this project as:

**Mehredad, AI-Driven Service Blueprint Analyzer (2024). Available at: [GitHub Repository](https://github.com/Mehredad/AI-DrivenServiceBlueprintAnalyzer).**

For academic or research use, please cite it as:
**Mehredad (2024). AI-Driven Service Blueprint Analyzer. GitHub. Retrieved from: https://github.com/Mehredad/AI-DrivenServiceBlueprintAnalyzer.**

## Contact
For any questions or issues, feel free to reach out via:
- **Email**: Design@mehrdad.uk
