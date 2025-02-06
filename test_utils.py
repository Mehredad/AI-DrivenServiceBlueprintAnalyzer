# # Unit tests for utility functions in the Blueprint Analyzer
import os
import pytest
from werkzeug.datastructures import FileStorage
from io import BytesIO
import utils

class TestUtilityFunctions:
    def test_allowed_file(self):
        """
        Test the allowed_file function to ensure it correctly validates file extensions.
        
        Test cases:
        - Verify allowed file extensions are accepted
        - Verify disallowed file extensions are rejected
        """
        # Test valid file extensions
        assert utils.allowed_file('test.jpg') == True
        assert utils.allowed_file('test.pdf') == True
        
        # Test invalid file extensions
        assert utils.allowed_file('test.exe') == False
        assert utils.allowed_file('test.doc') == False

    def test_construct_prompt(self, tmp_path):
        """
        Test the construct_prompt function to ensure it correctly builds a prompt.
        Args:
            tmp_path: Temporary directory provided by pytest for file operations
        
        Validates:
        - Prompt includes analysis name
        - Prompt includes blueprint file details
        - Prompt includes additional data
        """
        # Create mock file storage for blueprint
        blueprint_content = b"Sample Blueprint Content"
        blueprint_file = FileStorage(
            stream=BytesIO(blueprint_content),
            filename='blueprint.txt',
            content_type='text/plain'
        )
        # Create mock additional data
        additional_data = {
            'persona': FileStorage(
                stream=BytesIO(b"Persona Details"),
                filename='persona.txt',
                content_type='text/plain'
            )
        }

        # Generate prompt using utility function
        prompt = utils.construct_prompt(
            'Test Analysis', 
            blueprint_file, 
            additional_data, 
            str(tmp_path)
        )

        # Assertions to validate prompt construction
        assert 'Test Analysis' in prompt
        assert 'Blueprint File: blueprint.txt' in prompt
        assert 'Persona Content:' in prompt

    def test_parse_gemini_response(self):
        """
        Test the parse_gemini_response function with a sample AI-generated response.
        
        Validates:
        - Correct parsing of SWOT analysis
        - Correct parsing of improvements
        - Proper handling of response sections
        """
        # Sample AI response
        sample_response = """
        SWOT Analysis:
        Strengths:
        - Strong market positioning
        - Innovative technology

        Weaknesses:
        - Limited resources
        - High operational costs

        Opportunities:
        - Emerging market segments
        - Technology advancements

        Threats:
        - Competitive landscape
        - Economic uncertainties

        Improvements:
        1. Optimize resource allocation
        2. Develop strategic partnerships
        """

        # Parse the sample response
        swot, improvements = utils.parse_gemini_response(sample_response)

        # Validate SWOT sections
        assert len(swot['strengths']) == 2, "Should have 2 strengths"
        assert len(swot['weaknesses']) == 2, "Should have 2 weaknesses"
        assert len(swot['opportunities']) == 2, "Should have 2 opportunities"
        assert len(swot['threats']) == 2, "Should have 2 threats"
        
        # Validate improvements
        assert len(improvements) == 2, "Should have 2 improvements"

    def test_parse_response_edge_cases(self):
        """
        Test parse_gemini_response with edge cases and unusual inputs.
        
        Test cases:
        - Empty response
        - Malformed response without clear structure
        
        Ensures robust error handling
        """
        # Test empty response
        swot, improvements = utils.parse_gemini_response("")
        assert swot['strengths'] == ['Unable to extract strengths'], "Should handle empty response"
        assert improvements == ['Unable to extract specific improvements'], "Should provide default message"

        # Test malformed response
        malformed_response = "Random text without clear structure"
        swot, improvements = utils.parse_gemini_response(malformed_response)

        # Ensure some default content is returned
        assert len(swot['strengths']) > 0, "Should return non-empty strengths"
        assert len(improvements) > 0, "Should return non-empty improvements"