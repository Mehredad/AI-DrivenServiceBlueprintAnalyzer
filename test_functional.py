import unittest
import os
import sys
import tempfile
from io import BytesIO

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
import utils
from werkzeug.datastructures import FileStorage

class BlueprintAnalyzerFunctionalTest(unittest.TestCase):
    """
    Functional Testing for Blueprint Analyzer
    Focus on testing specific functional requirements
    """

    def setUp(self):
        """
        Set up test environment for functional tests
        """
        app.config['TESTING'] = True
        self.app = app.test_client()
        
        # Create temporary upload directory
        self.upload_folder = tempfile.mkdtemp()
        app.config['UPLOAD_FOLDER'] = self.upload_folder

    def tearDown(self):
        """
        Clean up after functional tests
        """
        # Remove temporary files
        for file in os.listdir(self.upload_folder):
            os.unlink(os.path.join(self.upload_folder, file))
        os.rmdir(self.upload_folder)

    def create_test_file(self, filename='test_blueprint.pdf', content=b'Test blueprint content'):
        """
        Helper method to create test files
        """
        # Create a file in the temporary directory
        filepath = os.path.join(self.upload_folder, filename)
        with open(filepath, 'wb') as f:
            f.write(content)
        
        # Return a file object
        return open(filepath, 'rb')

    def test_multiple_file_upload(self):
        """
        Test uploading multiple optional files
        """
        with (
            self.create_test_file() as blueprint,
            self.create_test_file('persona.pdf') as persona,
            self.create_test_file('kpis.pdf') as kpis
        ):
            response = self.app.post('/', data={
                'analysis_name': 'Multiple Files Test',
                'blueprint': (blueprint, 'test_blueprint.pdf'),
                'persona': (persona, 'persona.pdf'),
                'kpis': (kpis, 'kpis.pdf')
            }, content_type='multipart/form-data')

            # Verify response
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Analysis Results', response.data)

    def test_analysis_name_validation(self):
        """
        Test analysis name validation
        """
        # Modify app.py to handle empty analysis name
        # Add this validation in your route handler
        def validate_analysis_name(name):
            if not name or not name.strip():
                return False
            return True

        # Test with valid analysis name
        with self.create_test_file() as blueprint:
            response = self.app.post('/', data={
                'analysis_name': 'Valid Project Name',
                'blueprint': (blueprint, 'test_blueprint.pdf')
            }, content_type='multipart/form-data')

            self.assertEqual(response.status_code, 200)

        # Test with empty analysis name
        with self.create_test_file() as blueprint:
            response = self.app.post('/', data={
                'analysis_name': '',
                'blueprint': (blueprint, 'test_blueprint.pdf')
            }, content_type='multipart/form-data')

            # Modify this based on how you handle empty analysis names in app.py
            self.assertIn(b'Analysis name is required', response.data)

    def test_result_structure(self):
        """
        Verify the structure of analysis results
        """
        with self.create_test_file() as blueprint:
            response = self.app.post('/', data={
                'analysis_name': 'Result Structure Test',
                'blueprint': (blueprint, 'test_blueprint.pdf')
            }, content_type='multipart/form-data')

            # Check result page contains expected sections
            self.assertIn(b'Strengths', response.data)
            self.assertIn(b'Weaknesses', response.data)
            self.assertIn(b'Opportunities', response.data)
            self.assertIn(b'Threats', response.data)
            self.assertIn(b'Improvements', response.data)

if __name__ == '__main__':
    unittest.main()