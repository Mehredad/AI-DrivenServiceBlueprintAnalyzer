import unittest
import os
import sys
import tempfile
from io import BytesIO
from werkzeug.datastructures import FileStorage

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
import utils

class BlueprintAnalyzerTestCase(unittest.TestCase):
    """
    Comprehensive test suite for Blueprint Analyzer application
    """

    def setUp(self):
        """
        Set up test environment before each test method
        - Create a test client
        - Prepare temporary files and configuration
        """
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()
        
        # Create a temporary upload directory
        self.upload_folder = tempfile.mkdtemp()
        app.config['UPLOAD_FOLDER'] = self.upload_folder

    def tearDown(self):
        """
        Clean up after each test method
        - Remove temporary files and directories
        """
        # Remove temporary files
        for file in os.listdir(self.upload_folder):
            os.unlink(os.path.join(self.upload_folder, file))
        os.rmdir(self.upload_folder)

    def create_test_file(self, filename='test_blueprint.pdf', content=b'Test blueprint content'):
        """
        Helper method to create a test file for upload
        
        Args:
            filename (str): Name of the test file
            content (bytes): Content of the test file
        
        Returns:
            FileStorage: File-like object for upload
        """
        file = BytesIO(content)
        return FileStorage(
            stream=file,
            filename=filename,
            content_type='application/pdf'
        )

    def test_index_page_load(self):
        """
        Test that the index page loads successfully
        """
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AI-Powered Blueprint Analyzer', response.data)

    def test_file_upload_validation(self):
        """
        Test file upload validation
        - Ensure blueprint file is required
        - Test successful file upload
        """
        # Test without blueprint file (should fail)
        response = self.app.post('/', 
            data={'analysis_name': 'Test Project'},
            content_type='multipart/form-data'
        )
        self.assertIn(b'Blueprint file is required', response.data)

        # Test with valid file upload
        test_file = self.create_test_file()
        response = self.app.post('/', 
            data={
                'analysis_name': 'Test Project',
                'blueprint': test_file
            }, 
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 200)

    def test_utils_allowed_file(self):
        """
        Test file extension validation in utils
        """
        # Test allowed file extensions
        allowed_files = [
            'test.pdf', 'test.jpg', 'test.jpeg', 
            'test.png', 'test.txt'
        ]
        for filename in allowed_files:
            self.assertTrue(utils.allowed_file(filename), f"Failed for {filename}")

        # Test disallowed file extensions
        disallowed_files = [
            'test.doc', 'test.docx', 'test.xls', 
            'test.exe', 'test.zip'
        ]
        for filename in disallowed_files:
            self.assertFalse(utils.allowed_file(filename), f"Failed for {filename}")

    def test_construct_prompt(self):
        """
        Test prompt construction utility
        """
        # Create a test file
        test_file = self.create_test_file()
        
        # Prepare additional data
        additional_data = {
            'persona': self.create_test_file('persona.pdf'),
            'kpis': None,  # Test with optional file
        }

        # Construct prompt
        prompt = utils.construct_prompt(
            'Test Project', 
            test_file, 
            additional_data, 
            self.upload_folder
        )

        # Assertions
        self.assertIsNotNone(prompt)
        self.assertIn('Test Project', prompt)
        self.assertIn('Blueprint File: test_blueprint.pdf', prompt)

    def test_parse_gemini_response(self):
        """
        Test response parsing utility
        """
        # Test scenarios
        test_cases = [
            # Minimal valid response
            """
            Strengths:
            - Strong team collaboration
            - Clear project goals

            Weaknesses:
            - Limited resources
            - Communication gaps

            Opportunities:
            - Market expansion
            - New technology adoption

            Threats:
            - Competitive market
            - Economic uncertainties

            Improvements:
            1. Enhance communication protocols
            2. Invest in team training
            """,
            
            # Empty or invalid response
            "",
            None
        ]

        for response in test_cases:
            swot, improvements = utils.parse_gemini_response(response)
            
            # Check SWOT structure
            self.assertIn('strengths', swot)
            self.assertIn('weaknesses', swot)
            self.assertIn('opportunities', swot)
            self.assertIn('threats', swot)
            
            # Check improvements
            self.assertIsInstance(improvements, list)

if __name__ == '__main__':
    unittest.main()