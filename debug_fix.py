#!/usr/bin/env python3

# Quick fix to add debug logging to see what's happening
# Read the current repository processor file, add some debug prints, and save it

import re

with open('src/services/repository_processor_v2.py', 'r') as f:
    content = f.read()

# Add debug logging at start of _process_code_files_async
old_pattern = r'(async def _process_code_files_async\([^)]+\)[^{]*{[^}]*"""[^"]*""")'
new_debug = '''async def _process_code_files_async(self, 
                                      repo_path: Path, 
                                      repo_config: RepositoryConfig,
                                      analysis: Dict[str, Any],
                                      progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Process code files asynchronously without threading.
        
        Args:
            repo_path: Repository path
            repo_config: Repository configuration
            analysis: Repository analysis results
            
        Returns:
            Dict[str, Any]: Processing results
        """'''

# Add debug prints after the file filtering section (around line 1296)
debug_code = '''            
            print(f"DEBUG: Total code files found: {len(code_files)}")
            print(f"DEBUG: Filtered files count: {len(filtered_files)}")
            if len(filtered_files) > 0:
                print(f"DEBUG: First few filtered files:")
                for i, f in enumerate(filtered_files[:3]):
                    print(f"  {i+1}. {f.relative_to(repo_path)}")
            else:
                print("DEBUG: No files passed filtering!")
                
            '''

# Insert the debug code after the filtering section
pattern_to_find = r'(try:\s+if file_path\.stat\(\)\.st_size <= repo_config\.max_file_size:\s+filtered_files\.append\(file_path\)\s+except \(OSError, PermissionError\):\s+continue)'
replacement = r'\1' + debug_code

modified_content = re.sub(pattern_to_find, replacement, content, flags=re.DOTALL)

if modified_content != content:
    # Write the modified content back
    with open('src/services/repository_processor_v2.py', 'w') as f:
        f.write(modified_content)
    print("Added debug logging to repository processor!")
else:
    print("Pattern not found - adding debug manually after line 1296")
    
    # Find the line and add debug after it
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'continue' in line and i > 1290 and i < 1300:
            # Insert debug code after this line
            debug_lines = [
                '',
                '            print(f"DEBUG: Total code files found: {len(code_files)}")',
                '            print(f"DEBUG: Filtered files count: {len(filtered_files)}")',
                '            if len(filtered_files) > 0:',
                '                print(f"DEBUG: First few filtered files:")',
                '                for idx, f in enumerate(filtered_files[:3]):',
                '                    print(f"  {idx+1}. {f.relative_to(repo_path)}")',
                '            else:',
                '                print("DEBUG: No files passed filtering!")',
                ''
            ]
            
            # Insert the debug lines
            for j, debug_line in enumerate(debug_lines):
                lines.insert(i + 1 + j, debug_line)
            break
    
    # Write back
    with open('src/services/repository_processor_v2.py', 'w') as f:
        f.write('\n'.join(lines))
    print("Added debug logging manually!")