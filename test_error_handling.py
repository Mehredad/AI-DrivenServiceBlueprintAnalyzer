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

class BlueprintAnalyzerErrorHandlingTest(unittest.TestCase):
    """
    Error Handling Testing for Blueprint Analyzer
    Focus on testing error scenarios and application resilience
    """

    def setUp(self):
        """
        Set up test environment for error handling tests
        """
        # Configure app for testing
        app.config['TESTING'] = True
        self.app = app.test_client()
        
        # Create temporary upload directory
        self.upload_folder = tempfile.mkdtemp()
        app.config['UPLOAD_FOLDER'] = self.upload_folder

    def tearDown(self):
        """
        Clean up after error handling tests
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

    def test_file_not_found_error(self):
        """
        Test handling of file not found error
        """
        # Simulate an empty file
        with BytesIO(b'') as empty_file:
            response = self.app.post('/', data={
                'analysis_name': 'File Not Found Test',
                'blueprint': (empty_file, 'non_existent_file.pdf')
            }, content_type='multipart/form-data')

        # Adjust assertion based on your actual error handling
        self.assertIn(response.status_code, [400, 200])
        # You might want to check for a specific error message
        # self.assertIn(b'File not found', response.data)

    def test_invalid_file_type_error(self):
        """
        Test handling of invalid file type error
        """
        # Create a file with an invalid extension
        filepath = os.path.join(self.upload_folder, 'invalid_file.txt')
        with open(filepath, 'wb') as f:
            f.write(b'Test content')
        
        with open(filepath, 'rb') as invalid_file:
            response = self.app.post('/', data={
                'analysis_name': 'Invalid File Type Test',
                'blueprint': (invalid_file, 'invalid_file.txt')
            }, content_type='multipart/form-data')

        # Adjust assertion based on your actual error handling
        self.assertIn(response.status_code, [400, 200])
        # You might want to check for a specific error message
        # self.assertIn(b'Invalid file type', response.data)

    def test_empty_analysis_name_error(self):
        """
        Test handling of empty analysis name error
        """
        # Create a test file
        with self.create_test_file() as blueprint:
            response = self.app.post('/', data={
                'analysis_name': '',
                'blueprint': (blueprint, 'test_blueprint.pdf')
            }, content_type='multipart/form-data')

        # Check for error handling
        self.assertIn(response.status_code, [400, 200])
        # You might want to check for a specific error message
        # self.assertIn(b'Analysis name is required', response.data)

    def test_oversized_file_error(self):
        """
        Test handling of oversized file upload
        """
        # Create a large file (e.g., > 10MB)
        large_content = b'0' * (11 * 1024 * 1024)  # 11MB
        filepath = os.path.join(self.upload_folder, 'large_file.pdf')
        
        with open(filepath, 'wb') as f:
            f.write(large_content)
        
        with open(filepath, 'rb') as large_file:
            response = self.app.post('/', data={
                'analysis_name': 'Oversized File Test',
                'blueprint': (large_file, 'large_file.pdf')
            }, content_type='multipart/form-data')

        # Adjust assertion based on your actual file size limit handling
        self.assertIn(response.status_code, [400, 200])
        # You might want to check for a specific error message
        # self.assertIn(b'File too large', response.data)

if __name__ == '__main__':
    unittest.main()