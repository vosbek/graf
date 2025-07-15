"""
Intelligent code chunking system for optimal RAG performance.
Implements advanced chunking strategies with semantic boundary detection.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .tree_sitter_parser import CodeChunk, RelationshipInfo, SupportedLanguage, TreeSitterParser


@dataclass
class ChunkingConfig:
    """Configuration for code chunking strategies."""
    max_chunk_size: int = 1000
    min_chunk_size: int = 100
    overlap_size: int = 200
    preserve_functions: bool = True
    preserve_classes: bool = True
    include_imports: bool = True
    include_context: bool = True
    context_lines: int = 3
    semantic_splitting: bool = True
    complexity_threshold: float = 5.0


@dataclass
class EnhancedChunk:
    """Enhanced code chunk with additional context and metadata."""
    chunk: CodeChunk
    context_before: str
    context_after: str
    related_chunks: List[str]
    business_domain: Optional[str] = None
    importance_score: float = 0.0
    embedding_metadata: Dict = None
    
    def __post_init__(self):
        if self.embedding_metadata is None:
            self.embedding_metadata = {}


class CodeChunker:
    """Advanced code chunking with semantic boundary detection."""
    
    def __init__(self, config: ChunkingConfig = None):
        self.config = config or ChunkingConfig()
        self.parser = TreeSitterParser()
        self.business_domains = self._initialize_business_domains()
    
    def _initialize_business_domains(self) -> Dict[str, Set[str]]:
        """Initialize business domain classifications."""
        return {
            'authentication': {
                'auth', 'login', 'logout', 'signin', 'signup', 'password', 'token', 'jwt',
                'session', 'user', 'credential', 'verify', 'authenticate', 'authorize',
                'oauth', 'sso', 'ldap', 'saml', 'bearer', 'basic_auth'
            },
            'database': {
                'db', 'database', 'sql', 'query', 'select', 'insert', 'update', 'delete',
                'table', 'schema', 'model', 'orm', 'migration', 'connection', 'pool',
                'transaction', 'commit', 'rollback', 'index', 'foreign_key', 'primary_key'
            },
            'api': {
                'api', 'rest', 'graphql', 'endpoint', 'route', 'controller', 'handler',
                'request', 'response', 'http', 'get', 'post', 'put', 'patch', 'delete',
                'middleware', 'cors', 'rate_limit', 'swagger', 'openapi', 'json', 'xml'
            },
            'business_logic': {
                'business', 'logic', 'rule', 'workflow', 'process', 'service', 'domain',
                'entity', 'aggregate', 'repository', 'factory', 'strategy', 'command',
                'event', 'handler', 'validator', 'calculator', 'processor', 'manager'
            },
            'ui': {
                'ui', 'component', 'view', 'template', 'render', 'display', 'form',
                'button', 'input', 'modal', 'dialog', 'menu', 'navigation', 'layout',
                'style', 'css', 'html', 'dom', 'event', 'click', 'hover', 'focus'
            },
            'integration': {
                'integration', 'external', 'third_party', 'webhook', 'notification',
                'email', 'sms', 'push', 'queue', 'message', 'event', 'publish',
                'subscribe', 'kafka', 'rabbitmq', 'redis', 'cache', 'cdn', 'aws', 'azure'
            },
            'security': {
                'security', 'encrypt', 'decrypt', 'hash', 'ssl', 'tls', 'certificate',
                'key', 'secret', 'sanitize', 'validate', 'xss', 'csrf', 'injection',
                'firewall', 'permission', 'role', 'acl', 'audit', 'log', 'monitor'
            },
            'testing': {
                'test', 'spec', 'mock', 'stub', 'fixture', 'assert', 'expect', 'should',
                'unit', 'integration', 'e2e', 'scenario', 'given', 'when', 'then',
                'setup', 'teardown', 'before', 'after', 'describe', 'it', 'jest', 'pytest'
            },
            'configuration': {
                'config', 'setting', 'option', 'parameter', 'property', 'environment',
                'env', 'variable', 'constant', 'default', 'initialize', 'setup',
                'bootstrap', 'start', 'init', 'load', 'parse', 'validate', 'schema'
            },
            'monitoring': {
                'monitor', 'metric', 'log', 'trace', 'debug', 'error', 'warn', 'info',
                'alert', 'notification', 'dashboard', 'report', 'analytics', 'performance',
                'benchmark', 'profiler', 'health', 'status', 'ping', 'heartbeat'
            }
        }
    
    def chunk_file(self, file_path: str, content: str, language: SupportedLanguage) -> List[EnhancedChunk]:
        """
        Chunk a file with semantic boundary detection.
        
        Args:
            file_path: Path to the source file
            content: Source code content
            language: Programming language
            
        Returns:
            List of enhanced chunks
        """
        # Parse code into semantic units
        chunks, relationships = self.parser.parse_code(content, language, file_path)
        
        # Apply chunking strategies
        enhanced_chunks = []
        
        for chunk in chunks:
            # Check if chunk needs splitting
            if self._needs_splitting(chunk):
                split_chunks = self._split_large_chunk(chunk, content, language)
                for split_chunk in split_chunks:
                    enhanced_chunk = self._enhance_chunk(split_chunk, content, chunks, relationships)
                    enhanced_chunks.append(enhanced_chunk)
            else:
                enhanced_chunk = self._enhance_chunk(chunk, content, chunks, relationships)
                enhanced_chunks.append(enhanced_chunk)
        
        # Add contextual relationships
        self._add_contextual_relationships(enhanced_chunks, relationships)
        
        # Classify business domains
        self._classify_business_domains(enhanced_chunks)
        
        # Calculate importance scores
        self._calculate_importance_scores(enhanced_chunks)
        
        # Filter by minimum size and complexity
        filtered_chunks = self._filter_chunks(enhanced_chunks)
        
        return filtered_chunks
    
    def _needs_splitting(self, chunk: CodeChunk) -> bool:
        """Determine if a chunk needs to be split."""
        return (
            len(chunk.content) > self.config.max_chunk_size or
            chunk.complexity_score > self.config.complexity_threshold
        )
    
    def _split_large_chunk(self, chunk: CodeChunk, content: str, language: SupportedLanguage) -> List[CodeChunk]:
        """Split a large chunk into smaller semantic units."""
        split_chunks = []
        
        # If it's a class or large function, try to split by methods/nested functions
        if chunk.chunk_type in ['class_definition', 'class_declaration']:
            split_chunks = self._split_class_chunk(chunk, content, language)
        elif chunk.chunk_type in ['function_definition', 'function_declaration']:
            split_chunks = self._split_function_chunk(chunk, content, language)
        else:
            # Generic splitting by lines with semantic boundaries
            split_chunks = self._split_by_semantic_boundaries(chunk, content)
        
        return split_chunks if split_chunks else [chunk]
    
    def _split_class_chunk(self, chunk: CodeChunk, content: str, language: SupportedLanguage) -> List[CodeChunk]:
        """Split a class chunk by methods."""
        split_chunks = []
        
        # Parse the class content to find methods
        class_content = chunk.content
        try:
            method_chunks, _ = self.parser.parse_code(class_content, language, f"{chunk.id}_methods")
            
            for method_chunk in method_chunks:
                if method_chunk.chunk_type in ['function_definition', 'method_definition']:
                    # Adjust line numbers relative to original file
                    method_chunk.start_line += chunk.start_line
                    method_chunk.end_line += chunk.start_line
                    method_chunk.parent_id = chunk.id
                    split_chunks.append(method_chunk)
        except Exception:
            # If parsing fails, fall back to line-based splitting
            return self._split_by_semantic_boundaries(chunk, content)
        
        return split_chunks
    
    def _split_function_chunk(self, chunk: CodeChunk, content: str, language: SupportedLanguage) -> List[CodeChunk]:
        """Split a function chunk by logical blocks."""
        lines = chunk.content.split('\n')
        
        # Find logical blocks (try/catch, if/else, loops, etc.)
        blocks = self._find_logical_blocks(lines, language)
        
        split_chunks = []
        for i, block in enumerate(blocks):
            if len(block['content']) >= self.config.min_chunk_size:
                block_chunk = CodeChunk(
                    id=f"{chunk.id}_block_{i}",
                    content=block['content'],
                    language=chunk.language,
                    chunk_type=f"{chunk.chunk_type}_block",
                    name=f"{chunk.name}_block_{i}" if chunk.name else None,
                    start_line=chunk.start_line + block['start_line'],
                    end_line=chunk.start_line + block['end_line'],
                    start_byte=chunk.start_byte + block['start_byte'],
                    end_byte=chunk.start_byte + block['end_byte'],
                    parent_id=chunk.id,
                    complexity_score=self.parser._calculate_complexity(block['content'])
                )
                split_chunks.append(block_chunk)
        
        return split_chunks
    
    def _find_logical_blocks(self, lines: List[str], language: SupportedLanguage) -> List[Dict]:
        """Find logical blocks within code."""
        blocks = []
        current_block = []
        current_start = 0
        
        # Language-specific block indicators
        block_keywords = {
            SupportedLanguage.PYTHON: ['if', 'elif', 'else', 'try', 'except', 'finally', 'with', 'for', 'while', 'def', 'class'],
            SupportedLanguage.JAVASCRIPT: ['if', 'else', 'try', 'catch', 'finally', 'for', 'while', 'function', 'class'],
            SupportedLanguage.JAVA: ['if', 'else', 'try', 'catch', 'finally', 'for', 'while', 'switch', 'case']
        }
        
        keywords = block_keywords.get(language, block_keywords[SupportedLanguage.PYTHON])
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            
            # Check for block keywords
            is_block_start = any(stripped_line.startswith(keyword) for keyword in keywords)
            
            if is_block_start and current_block:
                # End current block
                block_content = '\n'.join(current_block)
                blocks.append({
                    'content': block_content,
                    'start_line': current_start,
                    'end_line': i - 1,
                    'start_byte': sum(len(line) + 1 for line in lines[:current_start]),
                    'end_byte': sum(len(line) + 1 for line in lines[:i])
                })
                current_block = []
                current_start = i
            
            current_block.append(line)
        
        # Add final block
        if current_block:
            block_content = '\n'.join(current_block)
            blocks.append({
                'content': block_content,
                'start_line': current_start,
                'end_line': len(lines) - 1,
                'start_byte': sum(len(line) + 1 for line in lines[:current_start]),
                'end_byte': sum(len(line) + 1 for line in lines)
            })
        
        return blocks
    
    def _split_by_semantic_boundaries(self, chunk: CodeChunk, content: str) -> List[CodeChunk]:
        """Split chunk by semantic boundaries (paragraphs, blank lines)."""
        lines = chunk.content.split('\n')
        split_chunks = []
        
        current_chunk_lines = []
        current_start = 0
        
        for i, line in enumerate(lines):
            current_chunk_lines.append(line)
            
            # Check for semantic boundary
            is_boundary = (
                line.strip() == '' or  # Blank line
                (i < len(lines) - 1 and lines[i + 1].strip() == '') or  # Next line is blank
                len('\n'.join(current_chunk_lines)) >= self.config.max_chunk_size
            )
            
            if is_boundary and len('\n'.join(current_chunk_lines)) >= self.config.min_chunk_size:
                # Create sub-chunk
                sub_chunk_content = '\n'.join(current_chunk_lines)
                sub_chunk = CodeChunk(
                    id=f"{chunk.id}_sub_{len(split_chunks)}",
                    content=sub_chunk_content,
                    language=chunk.language,
                    chunk_type=f"{chunk.chunk_type}_sub",
                    name=f"{chunk.name}_sub_{len(split_chunks)}" if chunk.name else None,
                    start_line=chunk.start_line + current_start,
                    end_line=chunk.start_line + i,
                    start_byte=chunk.start_byte + current_start,
                    end_byte=chunk.start_byte + i,
                    parent_id=chunk.id,
                    complexity_score=self.parser._calculate_complexity(sub_chunk_content)
                )
                split_chunks.append(sub_chunk)
                
                current_chunk_lines = []
                current_start = i + 1
        
        # Add final chunk
        if current_chunk_lines:
            sub_chunk_content = '\n'.join(current_chunk_lines)
            if len(sub_chunk_content) >= self.config.min_chunk_size:
                sub_chunk = CodeChunk(
                    id=f"{chunk.id}_sub_{len(split_chunks)}",
                    content=sub_chunk_content,
                    language=chunk.language,
                    chunk_type=f"{chunk.chunk_type}_sub",
                    name=f"{chunk.name}_sub_{len(split_chunks)}" if chunk.name else None,
                    start_line=chunk.start_line + current_start,
                    end_line=chunk.end_line,
                    start_byte=chunk.start_byte + current_start,
                    end_byte=chunk.end_byte,
                    parent_id=chunk.id,
                    complexity_score=self.parser._calculate_complexity(sub_chunk_content)
                )
                split_chunks.append(sub_chunk)
        
        return split_chunks
    
    def _enhance_chunk(self, chunk: CodeChunk, file_content: str, all_chunks: List[CodeChunk], relationships: List[RelationshipInfo]) -> EnhancedChunk:
        """Enhance a chunk with additional context and metadata."""
        # Extract context before and after
        context_before, context_after = self._extract_context(chunk, file_content)
        
        # Find related chunks
        related_chunks = self._find_related_chunks(chunk, all_chunks, relationships)
        
        # Prepare embedding metadata
        embedding_metadata = self._prepare_embedding_metadata(chunk, context_before, context_after)
        
        return EnhancedChunk(
            chunk=chunk,
            context_before=context_before,
            context_after=context_after,
            related_chunks=related_chunks,
            embedding_metadata=embedding_metadata
        )
    
    def _extract_context(self, chunk: CodeChunk, file_content: str) -> Tuple[str, str]:
        """Extract context lines before and after the chunk."""
        lines = file_content.split('\n')
        
        # Context before
        context_before_start = max(0, chunk.start_line - self.config.context_lines)
        context_before_lines = lines[context_before_start:chunk.start_line]
        context_before = '\n'.join(context_before_lines)
        
        # Context after
        context_after_end = min(len(lines), chunk.end_line + 1 + self.config.context_lines)
        context_after_lines = lines[chunk.end_line + 1:context_after_end]
        context_after = '\n'.join(context_after_lines)
        
        return context_before, context_after
    
    def _find_related_chunks(self, chunk: CodeChunk, all_chunks: List[CodeChunk], relationships: List[RelationshipInfo]) -> List[str]:
        """Find chunks related to the current chunk."""
        related_ids = set()
        
        # Add parent and children
        if chunk.parent_id:
            related_ids.add(chunk.parent_id)
        
        related_ids.update(chunk.children_ids)
        
        # Add relationship targets
        for rel in relationships:
            if rel.source_id == chunk.id:
                related_ids.add(rel.target_id)
            elif rel.target_id == chunk.id:
                related_ids.add(rel.source_id)
        
        # Find chunks with similar names or in same file
        for other_chunk in all_chunks:
            if other_chunk.id != chunk.id:
                # Same file proximity
                if abs(other_chunk.start_line - chunk.end_line) <= 10:
                    related_ids.add(other_chunk.id)
                
                # Similar names
                if chunk.name and other_chunk.name:
                    if self._calculate_name_similarity(chunk.name, other_chunk.name) > 0.5:
                        related_ids.add(other_chunk.id)
        
        return list(related_ids)
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        # Simple similarity based on common substrings
        if name1 == name2:
            return 1.0
        
        # Check for common prefixes/suffixes
        common_length = 0
        min_length = min(len(name1), len(name2))
        
        for i in range(min_length):
            if name1[i] == name2[i]:
                common_length += 1
            else:
                break
        
        return common_length / max(len(name1), len(name2))
    
    def _prepare_embedding_metadata(self, chunk: CodeChunk, context_before: str, context_after: str) -> Dict:
        """Prepare metadata for embedding generation."""
        metadata = {
            'chunk_type': chunk.chunk_type,
            'language': chunk.language.value,
            'name': chunk.name,
            'has_docstring': chunk.docstring is not None,
            'complexity_score': chunk.complexity_score,
            'line_count': chunk.end_line - chunk.start_line + 1,
            'has_context': bool(context_before or context_after),
            'imports': chunk.imports,
            'annotations': chunk.annotations
        }
        
        # Add content features
        content_lower = chunk.content.lower()
        metadata.update({
            'has_error_handling': 'try' in content_lower or 'catch' in content_lower or 'except' in content_lower,
            'has_loops': any(keyword in content_lower for keyword in ['for', 'while', 'loop']),
            'has_conditionals': any(keyword in content_lower for keyword in ['if', 'switch', 'case']),
            'has_async': any(keyword in content_lower for keyword in ['async', 'await', 'promise']),
            'has_database': any(keyword in content_lower for keyword in ['query', 'select', 'insert', 'update', 'delete']),
            'has_api_calls': any(keyword in content_lower for keyword in ['request', 'response', 'http', 'api']),
        })
        
        return metadata
    
    def _add_contextual_relationships(self, enhanced_chunks: List[EnhancedChunk], relationships: List[RelationshipInfo]):
        """Add contextual relationships between chunks."""
        chunk_map = {chunk.chunk.id: chunk for chunk in enhanced_chunks}
        
        for relationship in relationships:
            if relationship.source_id in chunk_map:
                source_chunk = chunk_map[relationship.source_id]
                if relationship.target_id not in source_chunk.related_chunks:
                    source_chunk.related_chunks.append(relationship.target_id)
            
            if relationship.target_id in chunk_map:
                target_chunk = chunk_map[relationship.target_id]
                if relationship.source_id not in target_chunk.related_chunks:
                    target_chunk.related_chunks.append(relationship.source_id)
    
    def _classify_business_domains(self, enhanced_chunks: List[EnhancedChunk]):
        """Classify chunks by business domain."""
        for enhanced_chunk in enhanced_chunks:
            chunk = enhanced_chunk.chunk
            content_lower = chunk.content.lower()
            
            # Check name-based classification
            name_lower = chunk.name.lower() if chunk.name else ""
            
            # Score each domain
            domain_scores = {}
            
            for domain, keywords in self.business_domains.items():
                score = 0
                for keyword in keywords:
                    # Higher weight for name matches
                    if keyword in name_lower:
                        score += 3
                    # Lower weight for content matches
                    if keyword in content_lower:
                        score += 1
                
                if score > 0:
                    domain_scores[domain] = score
            
            # Assign to highest scoring domain
            if domain_scores:
                best_domain = max(domain_scores.items(), key=lambda x: x[1])
                if best_domain[1] >= 2:  # Minimum threshold
                    enhanced_chunk.business_domain = best_domain[0]
    
    def _calculate_importance_scores(self, enhanced_chunks: List[EnhancedChunk]):
        """Calculate importance scores for chunks."""
        for enhanced_chunk in enhanced_chunks:
            chunk = enhanced_chunk.chunk
            score = 0.0
            
            # Base score from chunk type
            type_scores = {
                'class_definition': 1.0,
                'function_definition': 0.8,
                'method_definition': 0.6,
                'variable': 0.3,
                'import': 0.2
            }
            score += type_scores.get(chunk.chunk_type, 0.5)
            
            # Complexity bonus
            score += min(chunk.complexity_score * 0.1, 0.5)
            
            # Documentation bonus
            if chunk.docstring:
                score += 0.3
            
            # Public/private modifier
            if chunk.name:
                if not chunk.name.startswith('_'):
                    score += 0.2  # Public
                else:
                    score -= 0.1  # Private
            
            # Relationship bonus
            score += min(len(enhanced_chunk.related_chunks) * 0.1, 0.5)
            
            # Business domain bonus
            if enhanced_chunk.business_domain:
                score += 0.2
            
            enhanced_chunk.importance_score = score
    
    def _filter_chunks(self, enhanced_chunks: List[EnhancedChunk]) -> List[EnhancedChunk]:
        """Filter chunks based on size and quality criteria."""
        filtered = []
        
        for enhanced_chunk in enhanced_chunks:
            chunk = enhanced_chunk.chunk
            
            # Size filter
            if len(chunk.content) < self.config.min_chunk_size:
                continue
            
            # Quality filter
            if chunk.chunk_type == 'variable' and not chunk.name:
                continue
            
            # Empty or whitespace-only content
            if not chunk.content.strip():
                continue
            
            filtered.append(enhanced_chunk)
        
        return filtered
    
    def create_embeddings_text(self, enhanced_chunk: EnhancedChunk) -> str:
        """Create optimized text for embeddings."""
        chunk = enhanced_chunk.chunk
        parts = []
        
        # Add type and name
        if chunk.name:
            parts.append(f"{chunk.chunk_type}: {chunk.name}")
        else:
            parts.append(f"{chunk.chunk_type}")
        
        # Add docstring if available
        if chunk.docstring:
            parts.append(f"Documentation: {chunk.docstring}")
        
        # Add business domain if classified
        if enhanced_chunk.business_domain:
            parts.append(f"Domain: {enhanced_chunk.business_domain}")
        
        # Add context before (limited)
        if enhanced_chunk.context_before and self.config.include_context:
            context_lines = enhanced_chunk.context_before.split('\n')[-2:]  # Last 2 lines
            if context_lines:
                parts.append(f"Context: {' '.join(context_lines)}")
        
        # Add main content
        parts.append(f"Code: {chunk.content}")
        
        # Add imports if relevant
        if chunk.imports and self.config.include_imports:
            parts.append(f"Imports: {', '.join(chunk.imports)}")
        
        return '\n'.join(parts)
    
    def get_chunk_summary(self, enhanced_chunk: EnhancedChunk) -> str:
        """Get a human-readable summary of the chunk."""
        chunk = enhanced_chunk.chunk
        
        summary_parts = []
        
        # Basic info
        if chunk.name:
            summary_parts.append(f"{chunk.chunk_type.replace('_', ' ').title()}: {chunk.name}")
        else:
            summary_parts.append(f"{chunk.chunk_type.replace('_', ' ').title()}")
        
        # Location
        summary_parts.append(f"Lines {chunk.start_line + 1}-{chunk.end_line + 1}")
        
        # Language
        summary_parts.append(f"Language: {chunk.language.value}")
        
        # Complexity
        if chunk.complexity_score > 1:
            summary_parts.append(f"Complexity: {chunk.complexity_score:.1f}")
        
        # Business domain
        if enhanced_chunk.business_domain:
            summary_parts.append(f"Domain: {enhanced_chunk.business_domain}")
        
        # Documentation
        if chunk.docstring:
            summary_parts.append("Documented")
        
        # Relationships
        if enhanced_chunk.related_chunks:
            summary_parts.append(f"Related to {len(enhanced_chunk.related_chunks)} other chunks")
        
        return " | ".join(summary_parts)