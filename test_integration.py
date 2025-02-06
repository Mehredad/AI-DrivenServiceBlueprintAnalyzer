import unittest
import os
import sys
import tempfile
from io import BytesIO

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
import utils
import vertexai
from vertexai.generative_models import GenerativeModel

class BlueprintAnalyzerIntegrationTest(unittest.TestCase):
    """
    Integration Testing for Blueprint Analyzer
    Focus on testing interactions between components
    """

    def setUp(self):
        """
        Set up test environment for integration tests
        """
        app.config['TESTING'] = True
        self.app = app.test_client()
        
        # Create temporary upload directory
        self.upload_folder = tempfile.mkdtemp()
        app.config['UPLOAD_FOLDER'] = self.upload_folder

    def tearDown(self):
        """
        Clean up after integration tests
        """
        # Remove temporary files
        for file in os.listdir(self.upload_folder):
            os.unlink(os.path.join(self.upload_folder, file))
        os.rmdir(self.upload_folder)

    def create_test_file(self, filename='test_blueprint.pdf', content=b'Test blueprint content'):
        """
        Helper method to create test files
        """
        from werkzeug.datastructures import FileStorage
        file = BytesIO(content)
        return FileStorage(
            stream=file,
            filename=filename,
            content_type='application/pdf'
        )

    def test_prompt_construction_and_model_input(self):
        """
        Integration test for prompt construction and model input
        Verify that the prompt can be successfully created and processed
        """
        # Create test files
        blueprint = self.create_test_file()
        persona = self.create_test_file('persona.pdf')

        # Construct prompt
        additional_data = {
            'persona': persona,
            'kpis': None
        }
        
        prompt = utils.construct_prompt(
            'Integration Test Project', 
            blueprint, 
            additional_data, 
            self.upload_folder
        )

        # Verify prompt construction
        self.assertIsNotNone(prompt)
        self.assertIn('Integration Test Project', prompt)

        # Simulate model input (mock if needed)
        try:
            # Use the actual Vertex AI model (or mock)
            model = GenerativeModel(os.getenv('MODEL_NAME'))
            response = model.generate_content(
                contents=prompt,
                generation_config={
                    "max_output_tokens": 2048,
                    "temperature": 0.7,
                    "top_p": 0.8,
                }
            )

            # Verify response
            self.assertTrue(hasattr(response, 'text'))
            self.assertIsNotNone(response.text)

        except Exception as e:
            self.fail(f"Model generation failed: {e}")

    def test_end_to_end_workflow(self):
        """
        End-to-end integration test simulating full application workflow
        """
        # Simulate file upload
        with open(os.path.join(self.upload_folder, 'test_blueprint.pdf'), 'wb') as f:
            f.write(b'Test blueprint content')

        # Perform POST request
        response = self.app.post('/', data={
            'analysis_name': 'End-to-End Test',
            'blueprint': (open(os.path.join(self.upload_folder, 'test_blueprint.pdf'), 'rb'), 'test_blueprint.pdf')
        }, content_type='multipart/form-data')

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Analysis Results', response.data)

if __name__ == '__main__':
    unittest.main()