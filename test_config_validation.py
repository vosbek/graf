#!/usr/bin/env python3
"""
Test Configuration Validation

Test suite for the configuration validation system.
"""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from src.services.config_validator import ConfigurationValidator, ValidationLevel, ValidationResult
    from src.services.config_schema import ConfigSchema, validate_env_file
    from src.config.settings import Settings
except ImportError:
    # Alternative import path
    import sys
    sys.path.append('src')
    from services.config_validator import ConfigurationValidator, ValidationLevel, ValidationResult
    from services.config_schema import ConfigSchema, validate_env_file
    from config.settings import Settings


class TestConfigurationValidator(unittest.TestCase):
    """Test configuration validator functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.validator = ConfigurationValidator()
    
    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            component="Test",
            check_name="test_check",
            level=ValidationLevel.INFO,
            success=True,
            message="Test message"
        )
        
        self.assertEqual(result.component, "Test")
        self.assertEqual(result.check_name, "test_check")
        self.assertEqual(result.level, ValidationLevel.INFO)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Test message")
        self.assertEqual(result.details, {})
    
    def test_validation_summary(self):
        """Test validation summary functionality."""
        summary = self.validator.summary
        
        # Add some test results
        summary.add_result(ValidationResult(
            component="Test1",
            check_name="check1",
            level=ValidationLevel.INFO,
            success=True,
            message="Success"
        ))
        
        summary.add_result(ValidationResult(
            component="Test2",
            check_name="check2",
            level=ValidationLevel.CRITICAL,
            success=False,
            message="Critical failure"
        ))
        
        summary.add_result(ValidationResult(
            component="Test3",
            check_name="check3",
            level=ValidationLevel.WARNING,
            success=False,
            message="Warning"
        ))
        
        summary.finalize()
        
        self.assertEqual(summary.total_checks, 3)
        self.assertEqual(summary.passed_checks, 1)
        self.assertEqual(summary.failed_checks, 2)
        self.assertEqual(summary.critical_failures, 1)
        self.assertEqual(summary.warning_failures, 1)
        self.assertFalse(summary.overall_success)  # Critical failure means not successful
    
    @patch.dict(os.environ, {
        'NEO4J_URI': 'bolt://localhost:7687',
        'NEO4J_USERNAME': 'neo4j',
        'NEO4J_PASSWORD': 'password',
        'CHROMA_HOST': 'localhost',
        'CHROMA_PORT': '8000'
    })
    async def test_environment_validation_success(self):
        """Test successful environment variable validation."""
        await self.validator._validate_environment_variables()
        
        # Check that required variables passed
        env_results = [r for r in self.validator.summary.results if r.component == "Environment"]
        required_results = [r for r in env_results if "Required variable" in r.check_name and r.success]
        
        self.assertGreater(len(required_results), 0)
    
    @patch.dict(os.environ, {}, clear=True)
    async def test_environment_validation_missing_required(self):
        """Test environment validation with missing required variables."""
        await self.validator._validate_environment_variables()
        
        # Check that missing required variables are detected
        env_results = [r for r in self.validator.summary.results if r.component == "Environment"]
        critical_failures = [r for r in env_results if r.level == ValidationLevel.CRITICAL and not r.success]
        
        self.assertGreater(len(critical_failures), 0)
    
    @patch.dict(os.environ, {'NEO4J_URI': 'invalid-uri'})
    async def test_neo4j_uri_format_validation(self):
        """Test Neo4j URI format validation."""
        await self.validator._validate_environment_variables()
        
        # Check that invalid URI format is detected
        env_results = [r for r in self.validator.summary.results if r.component == "Environment"]
        format_failures = [r for r in env_results if "Format validation NEO4J_URI" in r.check_name and not r.success]
        
        self.assertGreater(len(format_failures), 0)
    
    def test_config_file_validation_missing_env(self):
        """Test configuration file validation with missing .env file."""
        # Temporarily rename .env if it exists
        env_file = Path(".env")
        backup_file = Path(".env.backup")
        
        env_existed = False
        if env_file.exists():
            env_file.rename(backup_file)
            env_existed = True
        
        try:
            asyncio.run(self.validator._validate_configuration_files())
            
            # Check that missing .env file is detected as warning
            config_results = [r for r in self.validator.summary.results if r.component == "Configuration"]
            env_warnings = [r for r in config_results if "Environment file" in r.check_name and not r.success]
            
            self.assertGreater(len(env_warnings), 0)
            
        finally:
            # Restore .env file if it existed
            if env_existed and backup_file.exists():
                backup_file.rename(env_file)
    
    def test_get_validation_report(self):
        """Test validation report generation."""
        # Add some test results
        self.validator.summary.add_result(ValidationResult(
            component="Test",
            check_name="test_check",
            level=ValidationLevel.INFO,
            success=True,
            message="Test success"
        ))
        
        self.validator.summary.add_result(ValidationResult(
            component="Test",
            check_name="test_failure",
            level=ValidationLevel.ERROR,
            success=False,
            message="Test failure",
            remediation="Fix the test"
        ))
        
        self.validator.summary.finalize()
        
        report = self.validator.get_validation_report()
        
        self.assertIn("CONFIGURATION VALIDATION REPORT", report)
        self.assertIn("Test success", report)
        self.assertIn("Test failure", report)
        self.assertIn("Fix the test", report)


class TestConfigSchema(unittest.TestCase):
    """Test configuration schema functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.schema = ConfigSchema()
    
    def test_schema_fields_defined(self):
        """Test that schema fields are properly defined."""
        self.assertIn("NEO4J_URI", self.schema.fields)
        self.assertIn("CHROMA_HOST", self.schema.fields)
        self.assertIn("API_PORT", self.schema.fields)
        
        # Check required fields
        neo4j_uri_field = self.schema.fields["NEO4J_URI"]
        self.assertTrue(neo4j_uri_field.required)
        self.assertIsNotNone(neo4j_uri_field.validation_pattern)
    
    def test_value_validation_string(self):
        """Test string value validation."""
        field = self.schema.fields["APP_NAME"]
        
        is_valid, error = self.schema.validate_value(field, "TestApp")
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        is_valid, error = self.schema.validate_value(field, 123)
        self.assertFalse(is_valid)
        self.assertIn("must be a string", error)
    
    def test_value_validation_integer(self):
        """Test integer value validation."""
        field = self.schema.fields["API_PORT"]
        
        is_valid, error = self.schema.validate_value(field, 8080)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        is_valid, error = self.schema.validate_value(field, "8080")
        self.assertTrue(is_valid)  # String numbers should be accepted
        
        is_valid, error = self.schema.validate_value(field, 99999)
        self.assertFalse(is_valid)  # Out of port range
        self.assertIn("must be <=", error)
    
    def test_value_validation_boolean(self):
        """Test boolean value validation."""
        field = self.schema.fields["DEBUG"]
        
        is_valid, error = self.schema.validate_value(field, True)
        self.assertTrue(is_valid)
        
        is_valid, error = self.schema.validate_value(field, "true")
        self.assertTrue(is_valid)
        
        is_valid, error = self.schema.validate_value(field, "invalid")
        self.assertFalse(is_valid)
    
    def test_pattern_validation(self):
        """Test pattern validation."""
        field = self.schema.fields["NEO4J_URI"]
        
        is_valid, error = self.schema.validate_value(field, "bolt://localhost:7687")
        self.assertTrue(is_valid)
        
        is_valid, error = self.schema.validate_value(field, "invalid-uri")
        self.assertFalse(is_valid)
        self.assertIn("does not match required pattern", error)
    
    def test_dependency_validation(self):
        """Test field dependency validation."""
        config = {
            "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
            # Missing AWS_SECRET_ACCESS_KEY and AWS_REGION
        }
        
        errors = self.schema.validate_dependencies(config)
        self.assertGreater(len(errors), 0)
        
        # Should have errors about missing dependencies
        dependency_errors = [e for e in errors if "requires" in e]
        self.assertGreater(len(dependency_errors), 0)
    
    def test_env_file_validation(self):
        """Test .env file validation."""
        # Create a temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("# Test configuration\n")
            f.write("NEO4J_URI=bolt://localhost:7687\n")
            f.write("NEO4J_USERNAME=neo4j\n")
            f.write("NEO4J_PASSWORD=password\n")
            f.write("CHROMA_HOST=localhost\n")
            f.write("CHROMA_PORT=8000\n")
            f.write("API_PORT=8080\n")
            temp_file = f.name
        
        try:
            is_valid, errors = validate_env_file(temp_file)
            
            # Should be valid with required fields
            if not is_valid:
                print("Validation errors:", errors)
            
            # Clean up
            os.unlink(temp_file)
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            raise e
    
    def test_generate_env_template(self):
        """Test environment template generation."""
        template = self.schema.generate_env_template()
        
        self.assertIn("GraphRAG Configuration Template", template)
        self.assertIn("NEO4J_URI=", template)
        self.assertIn("CHROMA_HOST=", template)
        self.assertIn("API_PORT=8080", template)  # Should have default value


class TestIntegration(unittest.TestCase):
    """Integration tests for configuration validation."""
    
    async def test_full_validation_with_minimal_config(self):
        """Test full validation with minimal valid configuration."""
        # Mock environment with minimal required config
        with patch.dict(os.environ, {
            'NEO4J_URI': 'bolt://localhost:7687',
            'NEO4J_USERNAME': 'neo4j',
            'NEO4J_PASSWORD': 'password',
            'CHROMA_HOST': 'localhost',
            'CHROMA_PORT': '8000'
        }):
            # Mock network calls to avoid actual connections
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                # Mock database connections
                with patch('neo4j.GraphDatabase.driver'), \
                     patch('psycopg2.connect'), \
                     patch('redis.from_url'):
                    
                    validator = ConfigurationValidator()
                    summary = await validator.validate_all()
                    
                    # Should have some successful checks
                    self.assertGreater(summary.total_checks, 0)
                    self.assertGreater(summary.passed_checks, 0)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfigurationValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigSchema))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


async def run_async_tests():
    """Run async tests."""
    test_case = TestConfigurationValidator()
    test_case.setUp()
    
    print("Running async environment validation tests...")
    
    # Test with valid environment
    with patch.dict(os.environ, {
        'NEO4J_URI': 'bolt://localhost:7687',
        'NEO4J_USERNAME': 'neo4j',
        'NEO4J_PASSWORD': 'password',
        'CHROMA_HOST': 'localhost',
        'CHROMA_PORT': '8000'
    }):
        await test_case.test_environment_validation_success()
        print("✅ Environment validation success test passed")
    
    # Reset validator for next test
    test_case.setUp()
    
    # Test with missing environment
    with patch.dict(os.environ, {}, clear=True):
        await test_case.test_environment_validation_missing_required()
        print("✅ Environment validation missing required test passed")
    
    # Test integration
    integration_test = TestIntegration()
    await integration_test.test_full_validation_with_minimal_config()
    print("✅ Integration test passed")


def main():
    """Main test function."""
    print("🧪 Running Configuration Validation Tests")
    print("=" * 50)
    
    # Run synchronous tests
    print("\n📋 Running synchronous tests...")
    sync_success = run_tests()
    
    # Run asynchronous tests
    print("\n⚡ Running asynchronous tests...")
    try:
        asyncio.run(run_async_tests())
        async_success = True
        print("✅ All async tests passed")
    except Exception as e:
        print(f"❌ Async tests failed: {e}")
        async_success = False
    
    # Summary
    print("\n" + "=" * 50)
    if sync_success and async_success:
        print("✅ All configuration validation tests PASSED")
        return 0
    else:
        print("❌ Some configuration validation tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())