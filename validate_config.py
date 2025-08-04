#!/usr/bin/env python3
"""
Standalone Configuration Validation Script

This script can be run independently to validate the GraphRAG system configuration
without starting the full application. Useful for troubleshooting and CI/CD pipelines.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.config_validator import ConfigurationValidator, validate_configuration


def setup_logging(level=logging.INFO):
    """Setup logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/config_validation.log', mode='w')
        ]
    )


async def main():
    """Main validation function."""
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)
    
    # Setup logging
    setup_logging(logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting GraphRAG configuration validation")
    
    try:
        # Run comprehensive validation
        summary = await validate_configuration()
        
        # Create validator instance for report generation
        validator = ConfigurationValidator()
        validator.summary = summary
        
        # Print summary to stdout
        print("\n" + "=" * 60)
        print("GRAPHRAG CONFIGURATION VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total checks: {summary.total_checks}")
        print(f"Passed: {summary.passed_checks}")
        print(f"Failed: {summary.failed_checks}")
        print(f"Critical failures: {summary.critical_failures}")
        print(f"Error failures: {summary.error_failures}")
        print(f"Warning failures: {summary.warning_failures}")
        print(f"Validation time: {summary.validation_time:.2f}s")
        print(f"Overall success: {'YES' if summary.overall_success else 'NO'}")
        print("=" * 60)
        
        # Print detailed report
        print("\nDETAILED VALIDATION REPORT:")
        print(validator.get_validation_report())
        
        # Print machine-readable output for scripts
        print(f"\nMACHINE_READABLE_OUTPUT:")
        print(f"CONFIG_VALIDATION_SUCCESS={summary.overall_success}")
        print(f"CONFIG_VALIDATION_TOTAL={summary.total_checks}")
        print(f"CONFIG_VALIDATION_PASSED={summary.passed_checks}")
        print(f"CONFIG_VALIDATION_FAILED={summary.failed_checks}")
        print(f"CONFIG_VALIDATION_CRITICAL={summary.critical_failures}")
        print(f"CONFIG_VALIDATION_ERRORS={summary.error_failures}")
        print(f"CONFIG_VALIDATION_WARNINGS={summary.warning_failures}")
        print(f"CONFIG_VALIDATION_TIME={summary.validation_time:.2f}")
        
        # Print specific recommendations
        if not summary.overall_success:
            print("\nRECOMMENDATIONS:")
            critical_results = [r for r in summary.results if not r.success and r.level == "CRITICAL"]
            error_results = [r for r in summary.results if not r.success and r.level == "ERROR"]
            
            if critical_results:
                print("\nCRITICAL ISSUES (must fix before starting):")
                for result in critical_results:
                    print(f"  • {result.component}: {result.message}")
                    if result.remediation:
                        print(f"    → {result.remediation}")
            
            if error_results:
                print("\nERROR ISSUES (may cause functionality problems):")
                for result in error_results:
                    print(f"  • {result.component}: {result.message}")
                    if result.remediation:
                        print(f"    → {result.remediation}")
        
        # Exit with appropriate code
        exit_code = 0 if summary.overall_success else 1
        logger.info(f"Configuration validation completed with exit code {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.error(f"Configuration validation failed with error: {str(e)}")
        print(f"\nVALIDATION ERROR: {str(e)}")
        print("CONFIG_VALIDATION_ERROR=True")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)