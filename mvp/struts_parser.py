"""
Struts-specific parser for MVP.
Extracts Struts configuration, actions, forms, and JSP patterns.
"""

import os
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import xml.etree.ElementTree as ET

import xmltodict

logger = logging.getLogger(__name__)


class StrutsParser:
    """Parser for Struts applications - config files, actions, and JSPs."""
    
    def __init__(self):
        self.action_pattern = re.compile(r'class\s+(\w+)\s+extends\s+(?:Action|DispatchAction|LookupDispatchAction)')
        self.form_pattern = re.compile(r'class\s+(\w+)\s+extends\s+(?:ActionForm|DynaActionForm|ValidatorForm)')
        self.execute_pattern = re.compile(r'public\s+ActionForward\s+execute\s*\([^)]*\)')
        self.forward_pattern = re.compile(r'return\s+mapping\.findForward\s*\(\s*["\']([^"\']+)["\']')
        self.jsp_tag_pattern = re.compile(r'<(\w+):(\w+)[^>]*>')
        
    def find_struts_files(self, repo_path: str) -> Dict[str, List[Path]]:
        """Find all Struts-related files in a repository."""
        repo_path = Path(repo_path)
        struts_files = {
            'config': [],
            'actions': [],
            'forms': [],
            'jsps': [],
            'properties': []
        }
        
        for file_path in repo_path.rglob("*"):
            if file_path.is_file():
                # Skip common build/temp directories
                if any(part in ['target', 'build', '.git', 'node_modules'] for part in file_path.parts):
                    continue
                
                # Categorize files
                if file_path.name == 'struts-config.xml':
                    struts_files['config'].append(file_path)
                elif file_path.suffix == '.java':
                    # Check if it's an Action or Form
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        if 'extends Action' in content or 'extends DispatchAction' in content:
                            struts_files['actions'].append(file_path)
                        elif 'extends ActionForm' in content or 'extends ValidatorForm' in content:
                            struts_files['forms'].append(file_path)
                    except Exception:
                        pass
                elif file_path.suffix in ['.jsp', '.tag', '.tagx']:
                    struts_files['jsps'].append(file_path)
                elif file_path.suffix == '.properties':
                    struts_files['properties'].append(file_path)
        
        logger.info(f"Found Struts files - Config: {len(struts_files['config'])}, "
                   f"Actions: {len(struts_files['actions'])}, Forms: {len(struts_files['forms'])}, "
                   f"JSPs: {len(struts_files['jsps'])}, Properties: {len(struts_files['properties'])}")
        
        return struts_files
    
    def parse_struts_config(self, config_path: Path) -> Dict[str, Any]:
        """Parse struts-config.xml file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse XML using xmltodict for easier access
            config_dict = xmltodict.parse(content)
            struts_config = config_dict.get('struts-config', {})
            
            result = {
                'file_path': str(config_path),
                'action_mappings': [],
                'form_beans': [],
                'forwards': [],
                'message_resources': []
            }
            
            # Extract action mappings
            action_mappings = struts_config.get('action-mappings', {}).get('action', [])
            if isinstance(action_mappings, dict):
                action_mappings = [action_mappings]
            
            for action in action_mappings:
                if isinstance(action, dict):
                    mapping = {
                        'path': action.get('@path', ''),
                        'type': action.get('@type', ''),
                        'name': action.get('@name', ''),
                        'scope': action.get('@scope', 'request'),
                        'validate': action.get('@validate', 'true'),
                        'input': action.get('@input', ''),
                        'forwards': []
                    }
                    
                    # Extract forwards for this action
                    forwards = action.get('forward', [])
                    if isinstance(forwards, dict):
                        forwards = [forwards]
                    
                    for forward in forwards:
                        if isinstance(forward, dict):
                            mapping['forwards'].append({
                                'name': forward.get('@name', ''),
                                'path': forward.get('@path', ''),
                                'redirect': forward.get('@redirect', 'false')
                            })
                    
                    result['action_mappings'].append(mapping)
            
            # Extract form beans
            form_beans = struts_config.get('form-beans', {}).get('form-bean', [])
            if isinstance(form_beans, dict):
                form_beans = [form_beans]
            
            for form_bean in form_beans:
                if isinstance(form_bean, dict):
                    result['form_beans'].append({
                        'name': form_bean.get('@name', ''),
                        'type': form_bean.get('@type', ''),
                        'dynamic': form_bean.get('@dynamic', 'false')
                    })
            
            # Extract global forwards
            global_forwards = struts_config.get('global-forwards', {}).get('forward', [])
            if isinstance(global_forwards, dict):
                global_forwards = [global_forwards]
            
            for forward in global_forwards:
                if isinstance(forward, dict):
                    result['forwards'].append({
                        'name': forward.get('@name', ''),
                        'path': forward.get('@path', ''),
                        'redirect': forward.get('@redirect', 'false'),
                        'scope': 'global'
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse struts-config.xml {config_path}: {e}")
            return {'file_path': str(config_path), 'error': str(e)}
    
    def parse_action_class(self, action_path: Path) -> Dict[str, Any]:
        """Parse a Struts Action class."""
        try:
            content = action_path.read_text(encoding='utf-8', errors='ignore')
            
            result = {
                'file_path': str(action_path),
                'class_name': action_path.stem,
                'package': '',
                'extends': '',
                'methods': [],
                'forwards_used': [],
                'form_used': '',
                'business_logic': []
            }
            
            # Extract package
            package_match = re.search(r'package\s+([\w.]+)', content)
            if package_match:
                result['package'] = package_match.group(1)
            
            # Extract class declaration
            class_match = re.search(r'class\s+(\w+)\s+extends\s+([\w.]+)', content)
            if class_match:
                result['class_name'] = class_match.group(1)
                result['extends'] = class_match.group(2)
            
            # Find execute methods and other public methods
            method_pattern = re.compile(r'public\s+(?:ActionForward|String|void)\s+(\w+)\s*\([^)]*\)\s*(?:throws[^{]*)?\{')
            for match in method_pattern.finditer(content):
                result['methods'].append(match.group(1))
            
            # Find forward usages
            forward_matches = self.forward_pattern.findall(content)
            result['forwards_used'] = list(set(forward_matches))
            
            # Find form usage (simplified)
            form_match = re.search(r'(\w+Form)\s+\w+\s*=\s*\([^)]+\)\s*form', content)
            if form_match:
                result['form_used'] = form_match.group(1)
            
            # Extract potential business logic (method calls, validations, etc.)
            business_logic_patterns = [
                r'\.validate\s*\(',
                r'\.save\s*\(',
                r'\.update\s*\(',
                r'\.delete\s*\(',
                r'\.find\s*\(',
                r'\.get\w+\s*\(',
                r'if\s*\([^)]*\.equals\s*\(',
                r'throw\s+new\s+\w+Exception'
            ]
            
            for pattern in business_logic_patterns:
                matches = re.findall(pattern, content)
                result['business_logic'].extend(matches)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse Action class {action_path}: {e}")
            return {'file_path': str(action_path), 'error': str(e)}
    
    def parse_jsp_file(self, jsp_path: Path) -> Dict[str, Any]:
        """Parse a JSP file for Struts tags and patterns."""
        try:
            content = jsp_path.read_text(encoding='utf-8', errors='ignore')
            
            result = {
                'file_path': str(jsp_path),
                'struts_tags': [],
                'forms': [],
                'actions_referenced': [],
                'data_accessed': []
            }
            
            # Find Struts tags
            tag_matches = self.jsp_tag_pattern.findall(content)
            for namespace, tag in tag_matches:
                if namespace in ['html', 'bean', 'logic', 'nested']:
                    result['struts_tags'].append(f"{namespace}:{tag}")
            
            # Find form actions
            form_actions = re.findall(r'<html:form[^>]*action\s*=\s*["\']([^"\']+)["\']', content)
            result['actions_referenced'] = list(set(form_actions))
            
            # Find bean:write and other data access patterns
            data_patterns = [
                r'<bean:write[^>]*property\s*=\s*["\']([^"\']+)["\']',
                r'\$\{(\w+(?:\.\w+)*)\}',  # EL expressions
                r'<c:out[^>]*value\s*=\s*["\'][^"\']*\$\{([^}]+)\}["\']'
            ]
            
            for pattern in data_patterns:
                matches = re.findall(pattern, content)
                result['data_accessed'].extend(matches)
            
            # Remove duplicates
            result['struts_tags'] = list(set(result['struts_tags']))
            result['data_accessed'] = list(set(result['data_accessed']))
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse JSP file {jsp_path}: {e}")
            return {'file_path': str(jsp_path), 'error': str(e)}
    
    def analyze_struts_application(self, repo_path: str) -> Dict[str, Any]:
        """Complete analysis of a Struts application."""
        struts_files = self.find_struts_files(repo_path)
        
        analysis = {
            'repository': repo_path,
            'config_analysis': [],
            'action_analysis': [],
            'jsp_analysis': [],
            'summary': {
                'total_actions': len(struts_files['actions']),
                'total_jsps': len(struts_files['jsps']),
                'total_configs': len(struts_files['config']),
                'total_forms': len(struts_files['forms'])
            }
        }
        
        # Parse configuration files
        for config_file in struts_files['config']:
            config_data = self.parse_struts_config(config_file)
            analysis['config_analysis'].append(config_data)
        
        # Parse action classes (limit to prevent overwhelming)
        for action_file in struts_files['actions'][:50]:  # Limit for performance
            action_data = self.parse_action_class(action_file)
            analysis['action_analysis'].append(action_data)
        
        # Parse JSP files (sample)
        for jsp_file in struts_files['jsps'][:20]:  # Sample for performance
            jsp_data = self.parse_jsp_file(jsp_file)
            analysis['jsp_analysis'].append(jsp_data)
        
        return analysis