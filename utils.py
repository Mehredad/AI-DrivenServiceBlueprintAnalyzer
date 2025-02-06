import os
import re
from werkzeug.utils import secure_filename

def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension.
    
    Args:
        filename (str): Name of the file to check
    
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    allowed_extensions = {'png', 'jpg', 'jpeg', 'pdf', 'txt'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def construct_prompt(analysis_name, blueprint_file, additional_data, upload_folder):
    """
    Constructs a comprehensive prompt for analyzing the service blueprint and/or uploaded diagrams based on uploaded files context.
    
    Args:
        analysis_name (str): Name of the analysis
        blueprint_file (FileStorage): The main blueprint file
        additional_data (dict): Dictionary of additional uploaded files
        upload_folder (str): Path to the upload folder
    
    Returns:
        str: Constructed prompt for AI analysis
    """
    def read_file_content(file):
        """
        Safely read file content, handling both text and binary files.
        
        Args:
            file (FileStorage): File to read
        
        Returns:
            str: File content or description
        """
        try:
            # Try to read as text
            content = file.read().decode('utf-8')
            file.seek(0)
            return content
        except UnicodeDecodeError:
            # For binary files, just return filename
            return f"[Binary file: {file.filename}]"

    # Initialize the prompt with analysis name
    prompt = f"Analysis Name: {analysis_name}\n\n"
    
    # Process and save blueprint file
    if blueprint_file:
        filename = secure_filename(blueprint_file.filename)
        filepath = os.path.join(upload_folder, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        blueprint_file.save(filepath)
        prompt += f"Blueprint File: {filename}\n"
        prompt += read_file_content(blueprint_file) + "\n\n"

    # Process additional data files
    for data_type, file in additional_data.items():
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            prompt += f"{data_type.capitalize()} Content:\n"
            prompt += read_file_content(file) + "\n\n"

    # Add structured analysis request
    prompt += """
    Considering the context of the uploaded diagrams (files), please analyze the uploaded service blueprint and any other additional materials. Structure your response as follows:

    Granular SWOT Analysis for each step of the blueprint or journey map:
    - Strengths:
    [List key strengths identified in the blueprint]
    - Weaknesses:
    [List key weaknesses identified in the blueprint]
    - Opportunities:
    [List key opportunities identified in the blueprint]
    - Threats:
    [List key threats identified in the blueprint]

    Improvements:
    1. [First improvement with detailed steps]
    2. [Second improvement with detailed steps]
    [Continue with numbered improvements as needed]

    If there is any existing related case study, provide a link to read and learn more about the potential improvements.

    Please focus on the user experience, pain points, and potential improvements relevant to the service blueprint.
    """
    return prompt

def parse_gemini_response(response_text):
    """
    Parse the Gemini model's response into two tuples.
    
    Args:
        response_text (str): Raw response from the model
    
    Returns:
        tuple: (swot_analysis, improvements)
    """
    print("Full Raw Response:", response_text)

    default_swot = {
        'strengths': ['No specific strengths identified in the current analysis'],
        'weaknesses': ['No specific weaknesses identified in the current analysis'],
        'opportunities': ['No specific opportunities identified in the current analysis'],
        'threats': ['No specific threats identified in the current analysis']
    }
    
    default_improvements = ['No specific improvements could be extracted from the analysis']

    if not response_text or not isinstance(response_text, str):
        print("Invalid or empty response received")
        return default_swot, default_improvements
    
    response_lower = response_text.lower()
    
    sections = {
        'strengths': ['strengths:', 'strength:'],
        'weaknesses': ['weaknesses:', 'weakness:'],
        'opportunities': ['opportunities:', 'opportunity:'],
        'threats': ['threats:', 'threat:']
    }
    
    swot_analysis = {key: [] for key in sections.keys()}
    improvements = []
    
    for category, keywords in sections.items():
        for keyword in keywords:
            start_index = response_lower.find(keyword)
            if start_index != -1:
                next_section_indices = []
                for other_keywords in [kw for section_kws in sections.values() for kw in section_kws if kw != keyword]:
                    next_index = response_lower.find(other_keywords, start_index + len(keyword))
                    if next_index != -1:
                        next_section_indices.append(next_index)

                end_index = min(next_section_indices) if next_section_indices else len(response_text)
                section_content = response_text[start_index + len(keyword):end_index].strip()
                items = [
                    item.strip() 
                    for item in re.split(r'\n-|\n•|\n\d+\.', section_content) 
                    if item.strip() and len(item.strip()) > 2
                ]
                swot_analysis[category] = items if items else swot_analysis[category]
                break

    improvements_keywords = [
        'improvements:', 'improvement:', 'recommendations:', 
        'recommendation:', 'action items:', 'next steps:'
    ]
    
    for keyword in improvements_keywords:
        improvements_index = response_lower.find(keyword)
        if improvements_index != -1:
            improvements_content = response_text[improvements_index + len(keyword):].strip()
            improvements = [
                item.strip() 
                for item in re.split(r'\n-|\n•|\n\d+\.', improvements_content) 
                if item.strip() and len(item.strip()) > 2
            ]
            if improvements:
                break

    final_swot = {
        category: items if items else default_swot[category]
        for category, items in swot_analysis.items()
    }
    
    final_improvements = improvements if improvements else default_improvements

    print("Parsed SWOT Analysis:", final_swot)
    print("Parsed Improvements:", final_improvements)

    return final_swot, final_improvements
