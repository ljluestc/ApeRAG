#!/usr/bin/env python3
"""
Automated Test Report Generator

Generates comprehensive test reports with detailed metrics including:
- Test coverage analysis
- Performance benchmarks
- Security scan results
- Code quality metrics
- System health status

Author: AI Assistant
Date: 2024
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import subprocess
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestReportGenerator:
    """Generate comprehensive test reports"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now()
        
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        print("Generating comprehensive test report...")
        
        report = {
            "timestamp": self.timestamp.isoformat(),
            "project": "ApeRAG",
            "version": "1.0.0",
            "sections": {}
        }
        
        # Generate each section
        report["sections"]["coverage"] = self._generate_coverage_report()
        report["sections"]["performance"] = self._generate_performance_report()
        report["sections"]["security"] = self._generate_security_report()
        report["sections"]["code_quality"] = self._generate_code_quality_report()
        report["sections"]["test_results"] = self._generate_test_results_report()
        report["sections"]["system_health"] = self._generate_system_health_report()
        
        # Calculate overall score
        report["overall_score"] = self._calculate_overall_score(report["sections"])
        
        return report
    
    def _generate_coverage_report(self) -> Dict[str, Any]:
        """Generate test coverage report"""
        print("  - Generating coverage report...")
        
        try:
            # Run coverage analysis
            result = subprocess.run([
                "python", "-m", "pytest", 
                "tests/", 
                "--cov=aperag", 
                "--cov-report=json", 
                "--cov-report=term-missing"
            ], capture_output=True, text=True, cwd=project_root)
            
            # Parse coverage data
            coverage_file = project_root / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                
                total_coverage = coverage_data["totals"]["percent_covered"]
                line_coverage = coverage_data["totals"]["covered_lines"]
                total_lines = coverage_data["totals"]["num_statements"]
                
                return {
                    "total_coverage": round(total_coverage, 2),
                    "covered_lines": line_coverage,
                    "total_lines": total_lines,
                    "missing_lines": coverage_data["totals"]["missing_lines"],
                    "status": "PASS" if total_coverage >= 90 else "FAIL",
                    "details": {
                        "files": len(coverage_data["files"]),
                        "branches_covered": coverage_data["totals"].get("covered_branches", 0),
                        "branches_total": coverage_data["totals"].get("num_branches", 0)
                    }
                }
        except Exception as e:
            return {
                "error": str(e),
                "status": "ERROR"
            }
    
    def _generate_performance_report(self) -> Dict[str, Any]:
        """Generate performance benchmark report"""
        print("  - Generating performance report...")
        
        try:
            # Run performance tests
            result = subprocess.run([
                "python", "-m", "pytest", 
                "tests/performance/", 
                "--benchmark-only", 
                "--benchmark-json=performance.json"
            ], capture_output=True, text=True, cwd=project_root)
            
            # Parse performance data
            perf_file = project_root / "performance.json"
            if perf_file.exists():
                with open(perf_file) as f:
                    perf_data = json.load(f)
                
                benchmarks = []
                for test in perf_data["benchmarks"]:
                    benchmarks.append({
                        "name": test["name"],
                        "mean": test["stats"]["mean"],
                        "std": test["stats"]["stddev"],
                        "min": test["stats"]["min"],
                        "max": test["stats"]["max"],
                        "iterations": test["stats"]["iterations"]
                    })
                
                return {
                    "benchmarks": benchmarks,
                    "total_tests": len(benchmarks),
                    "status": "PASS",
                    "summary": {
                        "fastest": min(benchmarks, key=lambda x: x["mean"]),
                        "slowest": max(benchmarks, key=lambda x: x["mean"])
                    }
                }
        except Exception as e:
            return {
                "error": str(e),
                "status": "ERROR"
            }
    
    def _generate_security_report(self) -> Dict[str, Any]:
        """Generate security scan report"""
        print("  - Generating security report...")
        
        try:
            # Run bandit security scan
            result = subprocess.run([
                "bandit", "-r", "aperag/", "-f", "json"
            ], capture_output=True, text=True, cwd=project_root)
            
            if result.returncode == 0:
                security_data = json.loads(result.stdout)
                
                issues = security_data.get("results", [])
                high_severity = len([i for i in issues if i["issue_severity"] == "HIGH"])
                medium_severity = len([i for i in issues if i["issue_severity"] == "MEDIUM"])
                low_severity = len([i for i in issues if i["issue_severity"] == "LOW"])
                
                return {
                    "total_issues": len(issues),
                    "high_severity": high_severity,
                    "medium_severity": medium_severity,
                    "low_severity": low_severity,
                    "status": "PASS" if high_severity == 0 else "FAIL",
                    "issues": issues[:10]  # Top 10 issues
                }
        except Exception as e:
            return {
                "error": str(e),
                "status": "ERROR"
            }
    
    def _generate_code_quality_report(self) -> Dict[str, Any]:
        """Generate code quality report"""
        print("  - Generating code quality report...")
        
        try:
            # Run ruff linter
            result = subprocess.run([
                "ruff", "check", "aperag/", "--output-format=json"
            ], capture_output=True, text=True, cwd=project_root)
            
            if result.returncode == 0:
                ruff_data = json.loads(result.stdout)
                
                issues = ruff_data.get("violations", [])
                error_count = len([i for i in issues if i["code"].startswith("E")])
                warning_count = len([i for i in issues if i["code"].startswith("W")])
                
                return {
                    "total_issues": len(issues),
                    "errors": error_count,
                    "warnings": warning_count,
                    "status": "PASS" if error_count == 0 else "FAIL",
                    "issues": issues[:10]  # Top 10 issues
                }
        except Exception as e:
            return {
                "error": str(e),
                "status": "ERROR"
            }
    
    def _generate_test_results_report(self) -> Dict[str, Any]:
        """Generate test results report"""
        print("  - Generating test results report...")
        
        try:
            # Run all tests
            result = subprocess.run([
                "python", "-m", "pytest", 
                "tests/", 
                "--junitxml=test-results.xml",
                "-v"
            ], capture_output=True, text=True, cwd=project_root)
            
            # Parse test results
            test_file = project_root / "test-results.xml"
            if test_file.exists():
                # Simple XML parsing for test results
                with open(test_file) as f:
                    content = f.read()
                
                # Extract basic stats
                total_tests = content.count('testcase')
                failures = content.count('failure')
                errors = content.count('error')
                skipped = content.count('skipped')
                
                return {
                    "total_tests": total_tests,
                    "passed": total_tests - failures - errors - skipped,
                    "failed": failures,
                    "errors": errors,
                    "skipped": skipped,
                    "success_rate": round((total_tests - failures - errors) / max(total_tests, 1) * 100, 2),
                    "status": "PASS" if failures == 0 and errors == 0 else "FAIL"
                }
        except Exception as e:
            return {
                "error": str(e),
                "status": "ERROR"
            }
    
    def _generate_system_health_report(self) -> Dict[str, Any]:
        """Generate system health report"""
        print("  - Generating system health report...")
        
        try:
            import psutil
            
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Check if services are running
            services_status = self._check_services()
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_usage": (disk.used / disk.total) * 100,
                "services": services_status,
                "status": "HEALTHY" if cpu_percent < 80 and memory.percent < 80 else "WARNING"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "ERROR"
            }
    
    def _check_services(self) -> Dict[str, str]:
        """Check status of required services"""
        services = {}
        
        # Check Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            services["redis"] = "RUNNING"
        except:
            services["redis"] = "STOPPED"
        
        # Check PostgreSQL
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                database="aperag",
                user="postgres",
                password="postgres"
            )
            conn.close()
            services["postgresql"] = "RUNNING"
        except:
            services["postgresql"] = "STOPPED"
        
        return services
    
    def _calculate_overall_score(self, sections: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall project score"""
        scores = []
        
        for section_name, section_data in sections.items():
            if "status" in section_data:
                if section_data["status"] == "PASS":
                    scores.append(100)
                elif section_data["status"] == "FAIL":
                    scores.append(0)
                else:
                    scores.append(50)  # Partial credit for warnings
        
        overall_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "score": round(overall_score, 2),
            "grade": self._get_grade(overall_score),
            "status": "EXCELLENT" if overall_score >= 90 else "GOOD" if overall_score >= 70 else "NEEDS_IMPROVEMENT"
        }
    
    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def save_report(self, report: Dict[str, Any], format: str = "json") -> str:
        """Save report to file"""
        timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        
        if format == "json":
            filename = f"test_report_{timestamp_str}.json"
            filepath = self.output_dir / filename
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
        
        elif format == "html":
            filename = f"test_report_{timestamp_str}.html"
            filepath = self.output_dir / filename
            html_content = self._generate_html_report(report)
            with open(filepath, 'w') as f:
                f.write(html_content)
        
        return str(filepath)
    
    def _generate_html_report(self, report: Dict[str, Any]) -> str:
        """Generate HTML report"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ApeRAG Test Report - {report['timestamp']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .pass {{ color: green; }}
                .fail {{ color: red; }}
                .warning {{ color: orange; }}
                .score {{ font-size: 24px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>ApeRAG Test Report</h1>
                <p>Generated: {report['timestamp']}</p>
                <p>Version: {report['version']}</p>
                <div class="score">
                    Overall Score: {report['overall_score']['score']}/100 ({report['overall_score']['grade']})
                </div>
            </div>
        """
        
        for section_name, section_data in report['sections'].items():
            status_class = section_data.get('status', 'unknown').lower()
            html += f"""
            <div class="section">
                <h2>{section_name.title()}</h2>
                <p class="{status_class}">Status: {section_data.get('status', 'Unknown')}</p>
                <pre>{json.dumps(section_data, indent=2)}</pre>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Generate comprehensive test report")
    parser.add_argument("--output-dir", default="reports", help="Output directory for reports")
    parser.add_argument("--format", choices=["json", "html", "both"], default="both", help="Report format")
    
    args = parser.parse_args()
    
    generator = TestReportGenerator(args.output_dir)
    report = generator.generate_comprehensive_report()
    
    # Save reports
    if args.format in ["json", "both"]:
        json_path = generator.save_report(report, "json")
        print(f"JSON report saved to: {json_path}")
    
    if args.format in ["html", "both"]:
        html_path = generator.save_report(report, "html")
        print(f"HTML report saved to: {html_path}")
    
    # Print summary
    print(f"\nOverall Score: {report['overall_score']['score']}/100 ({report['overall_score']['grade']})")
    print(f"Status: {report['overall_score']['status']}")


if __name__ == "__main__":
    main()
