"""
Simple query engine with fuzzy matching for ghops.

Provides an intuitive query language with fuzzy matching support
for querying repository metadata.
"""

from typing import Any, Dict, Tuple, Union, List
import operator
import logging
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

class SimpleQuery:
    """Dead simple query with fuzzy matching support."""
    
    def __init__(self, query_str: str):
        logger.debug(f"Initializing SimpleQuery with: {query_str}")
        self.parts = self._parse(query_str)
        logger.debug(f"Parsed query AST: {self.parts}")
    
    def _parse(self, query_str: str) -> Union[Tuple, str]:
        """Parse query into simple components."""
        logger.debug(f"_parse called with: {query_str}")
        # Handle NOT first
        if query_str.strip().startswith('not '):
            inner = query_str.strip()[4:]
            logger.debug(f"Found NOT operator, parsing inner: {inner}")
            return ('not', self._parse(inner))
        
        # Split by 'and' and 'or' (keeping track of which)
        # Simple approach - no nested parentheses for now
        if ' and ' in query_str:
            conditions = query_str.split(' and ')
            logger.debug(f"Found AND operator, splitting into {len(conditions)} conditions")
            return ('and', [self._parse_condition(c.strip()) for c in conditions])
        elif ' or ' in query_str:
            conditions = query_str.split(' or ')
            logger.debug(f"Found OR operator, splitting into {len(conditions)} conditions")
            return ('or', [self._parse_condition(c.strip()) for c in conditions])
        else:
            logger.debug(f"No boolean operators found, parsing as single condition")
            return self._parse_condition(query_str.strip())
    
    def _parse_condition(self, condition: str) -> Tuple:
        """Parse a single condition."""
        logger.debug(f"_parse_condition called with: {condition}")
        # Check for operators (order matters - check compound ops first)
        for op in ['~=', '==', '!=', '>=', '<=', '>', '<', ' contains ', ' in ']:
            if op in condition:
                path, value = condition.split(op, 1)
                path = path.strip()
                value = value.strip()
                
                # Special handling for 'in' operator - swap operands if left side is quoted
                if op.strip() == 'in' and (path.startswith("'") or path.startswith('"')):
                    # Swap: 'value' in path -> path contains 'value'
                    path, value = value, path
                    op = ' contains '
                
                # Remove quotes from values
                path = path.strip("'\"")
                value = value.strip("'\"")
                
                # Parse value to appropriate type
                parsed_value = self._parse_value(value)
                
                logger.debug(f"Parsed condition: path='{path}', op='{op.strip()}', value='{parsed_value}'")
                return (path, op.strip(), parsed_value)
        
        # If no operator, assume it's a simple text search
        logger.debug(f"No operator found, treating as simple text search: {condition}")
        return ('_simple', condition.strip("'\""))
    
    def _parse_value(self, value_str: str) -> Any:
        """Parse string values into Python types."""
        # Try to parse as number
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass
        
        # Boolean
        if value_str.lower() == 'true':
            return True
        elif value_str.lower() == 'false':
            return False
        
        # List (simple parsing)
        if value_str.startswith('[') and value_str.endswith(']'):
            items = value_str[1:-1].split(',')
            return [item.strip().strip("'\"") for item in items if item.strip()]
        
        # Default to string
        return value_str
    
    def evaluate(self, data: Dict[str, Any], threshold: int = 80) -> bool:
        """Evaluate query against data with fuzzy matching."""
        logger.debug(f"Evaluating query against data with keys: {list(data.keys())}")
        result = self._eval(self.parts, data, threshold)
        logger.debug(f"Query evaluation result: {result}")
        return result
    
    def _eval(self, node, data, threshold) -> bool:
        """Recursively evaluate the query tree."""
        logger.debug(f"_eval called with node: {node}")
        if isinstance(node, tuple):
            if node[0] == 'and':
                return all(self._eval(part, data, threshold) for part in node[1])
            elif node[0] == 'or':
                return any(self._eval(part, data, threshold) for part in node[1])
            elif node[0] == 'not':
                return not self._eval(node[1], data, threshold)
            elif node[0] == '_simple':
                # Simple text search across all string values
                search_term = node[1].lower()
                return self._fuzzy_search_anywhere(data, search_term, threshold)
            else:
                # It's a condition tuple (path, op, value)
                path, op, value = node
                actual = self._get_path(data, path)
                logger.debug(f"Evaluating condition: {path} {op} {value}, actual value: {actual}")
                
                # Apply operator with fuzzy support
                if op == '~=':  # Fuzzy equals
                    return self._fuzzy_match(str(actual), str(value), threshold)
                elif op == '==':
                    return self._compare_values(actual, value, operator.eq)
                elif op == '!=':
                    return self._compare_values(actual, value, operator.ne)
                elif op == 'contains':
                    return self._fuzzy_contains(actual, value, threshold)
                elif op == 'in':
                    return self._fuzzy_in(value, actual, threshold)
                elif op in ['>', '<', '>=', '<=']:
                    ops = {
                        '>': operator.gt,
                        '<': operator.lt,
                        '>=': operator.ge,
                        '<=': operator.le
                    }
                    try:
                        return ops[op](float(actual), float(value))
                    except (ValueError, TypeError):
                        return False
        
        return False
    
    def _compare_values(self, actual: Any, expected: Any, op) -> bool:
        """Compare values with type coercion."""
        # Handle None
        if actual is None:
            return op(actual, expected)
        
        # String comparison (case insensitive)
        if isinstance(expected, str) and not isinstance(actual, bool):
            return op(str(actual).lower(), expected.lower())
        
        # Direct comparison
        return op(actual, expected)
    
    def _fuzzy_match(self, actual: str, expected: str, threshold: int) -> bool:
        """Fuzzy string matching."""
        return fuzz.ratio(actual.lower(), expected.lower()) >= threshold
    
    def _fuzzy_contains(self, container, item: Any, threshold: int) -> bool:
        """Fuzzy contains check."""
        if container is None:
            return False
            
        if isinstance(container, list):
            # Check if any item in list fuzzy matches
            return any(
                fuzz.partial_ratio(str(i).lower(), str(item).lower()) >= threshold 
                for i in container
            )
        else:
            # Fuzzy substring match
            return fuzz.partial_ratio(str(container).lower(), str(item).lower()) >= threshold
    
    def _fuzzy_in(self, item: Any, container, threshold: int) -> bool:
        """Reverse of fuzzy contains."""
        return self._fuzzy_contains(container, item, threshold)
    
    def _fuzzy_search_anywhere(self, data: Any, search_term: str, threshold: int) -> bool:
        """Search for term anywhere in the data structure."""
        if isinstance(data, dict):
            for k, v in data.items():
                # Check key
                if fuzz.partial_ratio(k.lower(), search_term) >= threshold:
                    return True
                # Check value
                if self._fuzzy_search_anywhere(v, search_term, threshold):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._fuzzy_search_anywhere(item, search_term, threshold):
                    return True
        elif data is not None:
            # Leaf value
            if fuzz.partial_ratio(str(data).lower(), search_term) >= threshold:
                return True
        return False
    
    def _get_path(self, data, path) -> Any:
        """Get value at path, with fuzzy key matching."""
        logger.debug(f"Getting path '{path}' from data")
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                # Try exact match first
                if part in current:
                    current = current[part]
                else:
                    # Fuzzy match on keys
                    best_match = None
                    best_score = 0
                    for key in current.keys():
                        score = fuzz.ratio(part.lower(), key.lower())
                        if score > best_score and score >= 70:  # 70% threshold for keys
                            best_score = score
                            best_match = key
                    
                    if best_match:
                        current = current[best_match]
                    else:
                        return None
            else:
                return None
                
        return current


def query_repositories(repos: List[Dict[str, Any]], query_str: str, 
                      threshold: int = 80) -> List[Dict[str, Any]]:
    """
    Query a list of repositories using the simple query language.
    
    Args:
        repos: List of repository metadata dictionaries
        query_str: Query string
        threshold: Fuzzy matching threshold (0-100)
        
    Returns:
        Filtered list of repositories matching the query
    """
    if not query_str:
        return repos
        
    q = SimpleQuery(query_str)
    return [repo for repo in repos if q.evaluate(repo, threshold)]