"""
Unit tests for ghops.config module
"""
import unittest
import tempfile
import os
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from ghops.config import (
    load_config,
    save_config,
    generate_config_example,
    get_default_config
)


class TestConfigManagement(unittest.TestCase):
    """Test configuration management functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
    
    def tearDown(self):
        """Clean up test environment"""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir)
    
    def test_get_default_config(self):
        """Test default configuration structure"""
        config = get_default_config()
        
        # Check that all required sections exist
        self.assertIn('pypi', config)
        self.assertIn('social_media', config)
        self.assertIn('logging', config)
        
        # Check PyPI config
        self.assertIn('check_by_default', config['pypi'])
        self.assertTrue(config['pypi']['check_by_default'])
        
        # Check social media config
        self.assertIn('platforms', config['social_media'])
        self.assertIn('posting', config['social_media'])
        
        # Check logging config
        self.assertIn('level', config['logging'])
        self.assertIn('format', config['logging'])
    
    def test_load_config_no_file(self):
        """Test loading config when no file exists"""
        config = load_config()
        
        # Should return default config
        default_config = get_default_config()
        self.assertEqual(config['pypi']['check_by_default'], 
                        default_config['pypi']['check_by_default'])
    
    def test_load_config_json_file(self):
        """Test loading config from JSON file"""
        config_data = {
            'pypi': {'check_by_default': False},
            'logging': {'level': 'DEBUG'}
        }
        
        config_path = Path(self.temp_dir) / '.ghopsrc'
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        config = load_config()
        
        self.assertFalse(config['pypi']['check_by_default'])
        self.assertEqual(config['logging']['level'], 'DEBUG')
    
    def test_load_config_toml_file(self):
        """Test loading config from TOML file"""
        config_content = """
[pypi]
check_by_default = false

[logging]
level = "DEBUG"
"""
        
        config_path = Path(self.temp_dir) / '.ghopsrc.toml'
        config_path.write_text(config_content)
        
        config = load_config()
        
        self.assertFalse(config['pypi']['check_by_default'])
        self.assertEqual(config['logging']['level'], 'DEBUG')
    
    @patch.dict(os.environ, {'GHOPS_PYPI_CHECK_BY_DEFAULT': 'false'})
    def test_environment_override(self):
        """Test environment variable override"""
        config = load_config()
        
        # Environment should override config file
        self.assertFalse(config['pypi']['check_by_default'])
    
    @patch.dict(os.environ, {'GHOPS_SOCIAL_MEDIA_PLATFORMS_TWITTER_ENABLED': 'false'})
    def test_nested_environment_override(self):
        """Test nested environment variable override"""
        config = load_config()
        
        # Check nested override
        self.assertFalse(config['social_media']['platforms']['twitter']['enabled'])
    
    def test_save_config_json(self):
        """Test saving config to JSON file"""
        config_data = {
            'pypi': {'check_by_default': False},
            'logging': {'level': 'DEBUG'}
        }
        
        save_config(config_data)
        
        config_path = Path(self.temp_dir) / '.ghopsrc'
        self.assertTrue(config_path.exists())
        
        with open(config_path, 'r') as f:
            saved_config = json.load(f)
        
        self.assertEqual(saved_config['pypi']['check_by_default'], False)
        self.assertEqual(saved_config['logging']['level'], 'DEBUG')
    
    @patch('ghops.config.console')
    def test_generate_config_example(self, mock_console):
        """Test config example generation"""
        generate_config_example()
        
        config_path = Path(self.temp_dir) / '.ghopsrc.example'
        self.assertTrue(config_path.exists())
        
        # Verify console output
        mock_console.print.assert_called()
        call_args = mock_console.print.call_args_list[0][0][0]
        self.assertIn('example configuration file has been saved', call_args.lower())


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation"""
    
    def test_merge_configs(self):
        """Test configuration merging"""
        from ghops.config import merge_configs
        
        base_config = {
            'pypi': {'check_by_default': True, 'timeout': 30},
            'logging': {'level': 'INFO'}
        }
        
        override_config = {
            'pypi': {'check_by_default': False},
            'new_section': {'key': 'value'}
        }
        
        merged = merge_configs(base_config, override_config)
        
        # Should preserve base values not overridden
        self.assertEqual(merged['pypi']['timeout'], 30)
        self.assertEqual(merged['logging']['level'], 'INFO')
        
        # Should override specified values
        self.assertFalse(merged['pypi']['check_by_default'])
        
        # Should add new sections
        self.assertEqual(merged['new_section']['key'], 'value')


if __name__ == '__main__':
    unittest.main()
