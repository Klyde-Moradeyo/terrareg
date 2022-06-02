
import unittest.mock
import pytest
import sqlalchemy
from terrareg.database import Database

from terrareg.models import Module, Namespace, ModuleProvider, ModuleVersion
import terrareg.errors
from test.integration.terrareg import TerraregIntegrationTest

class TestModuleVersion(TerraregIntegrationTest):

    @pytest.mark.parametrize('version', [
        'astring',
        '',
        '1',
        '1.1',
        '.23.1',
        '1.1.1.1',
        '1.1.1.',
        '1.2.3-dottedsuffix1.2',
        '1.2.3-invalid-suffix',
        '1.0.9-'
    ])
    def test_invalid_module_versions(self, version):
        """Test invalid module versions"""
        namespace = Namespace(name='test')
        module = Module(namespace=namespace, name='test')
        module_provider = ModuleProvider(module=module, name='test')
        with pytest.raises(terrareg.errors.InvalidVersionError):
            ModuleVersion(module_provider=module_provider, version=version)

    @pytest.mark.parametrize('version,beta', [
        ('1.1.1', False),
        ('13.14.16', False),
        ('1.10.10', False),
        ('01.01.01', False),  # @TODO Should this be allowed?
        ('1.2.3-alpha', True),
        ('1.2.3-beta', True),
        ('1.2.3-anothersuffix1', True),
        ('1.2.2-123', True)
    ])
    def test_valid_module_versions(self, version, beta):
        """Test valid module versions"""
        namespace = Namespace(name='test')
        module = Module(namespace=namespace, name='test')
        module_provider = ModuleProvider(module=module, name='test')
        module_version = ModuleVersion(module_provider=module_provider, version=version)
        assert module_version._extracted_beta_flag == beta

    def test_create_db_row(self):
        """Test creating DB row"""
        namespace = Namespace(name='testcreation')
        module = Module(namespace=namespace, name='test-module')
        module_provider = ModuleProvider.get(module=module, name='testprovider', create=True)
        module_provider_row = module_provider._get_db_row()

        module_version = ModuleVersion(module_provider=module_provider, version='1.0.0')

        # Ensure that no DB row is returned for new module version
        assert module_version._get_db_row() == None

        # Insert module version into database
        module_version._create_db_row()

        # Ensure that a DB row is now returned
        new_db_row = module_version._get_db_row()
        assert new_db_row['module_provider_id'] == module_provider_row['id']
        assert type(new_db_row['id']) == int

        assert new_db_row['published'] == False
        assert new_db_row['version'] == '1.0.0'

        assert new_db_row['beta'] == False

        for attr in ['description', 'module_details', 'owner',
                     'published_at', 'readme_content', 'repo_base_url_template',
                     'repo_browse_url_template', 'repo_clone_url_template',
                     'variable_template']:
            assert new_db_row[attr] == None

    def test_create_beta_version(self):
        """Test creating DB row for beta version"""
        namespace = Namespace(name='testcreation')
        module = Module(namespace=namespace, name='test-module')
        module_provider = ModuleProvider.get(module=module, name='testprovider', create=True)
        module_provider_row = module_provider._get_db_row()

        module_version = ModuleVersion(module_provider=module_provider, version='1.0.0-beta')

        # Ensure that no DB row is returned for new module version
        assert module_version._get_db_row() == None

        # Insert module version into database
        module_version._create_db_row()

        # Ensure that a DB row is now returned
        new_db_row = module_version._get_db_row()
        assert new_db_row['module_provider_id'] == module_provider_row['id']
        assert type(new_db_row['id']) == int

        assert new_db_row['published'] == False
        assert new_db_row['version'] == '1.0.0-beta'

        assert new_db_row['beta'] == True

        for attr in ['description', 'module_details', 'owner',
                     'published_at', 'readme_content', 'repo_base_url_template',
                     'repo_browse_url_template', 'repo_clone_url_template',
                     'variable_template']:
            assert new_db_row[attr] == None

    def test_create_db_row_replace_existing(self):
        """Test creating DB row with pre-existing module version"""

        db = Database.get()

        with db.get_engine().connect() as conn:
            conn.execute(db.module_provider.insert().values(
                id=10000,
                namespace='testcreation',
                module='test-module',
                provider='testprovider'
            ))

            conn.execute(db.module_version.insert().values(
                id=10001,
                module_provider_id=10000,
                version='1.1.0',
                published=True,
                beta=False,
                internal=False
            ))

            # Create submodules
            conn.execute(db.sub_module.insert().values(
                id=10002,
                parent_module_version=10001,
                type='example',
                path='example/test-modal-db-row-create-here'
            ))
            conn.execute(db.sub_module.insert().values(
                id=10003,
                parent_module_version=10001,
                type='submodule',
                path='modules/test-modal-db-row-create-there'
            ))

            # Create example file
            conn.execute(db.example_file.insert().values(
                id=10004,
                submodule_id=10002,
                path='testfile.tf',
                content=None
            ))


        namespace = Namespace(name='testcreation')
        module = Module(namespace=namespace, name='test-module')
        module_provider = ModuleProvider.get(module=module, name='testprovider')
        module_provider_row = module_provider._get_db_row()

        module_version = ModuleVersion(module_provider=module_provider, version='1.1.0')

        # Ensure that pre-existing row is returned
        pre_existing_row = module_version._get_db_row()
        assert pre_existing_row is not None
        assert pre_existing_row['id'] == 10001

        # Insert module version into database
        module_version._create_db_row()

        # Ensure that a DB row is now returned
        new_db_row = module_version._get_db_row()
        assert new_db_row['module_provider_id'] == module_provider_row['id']
        assert type(new_db_row['id']) == int

        assert new_db_row['published'] == False
        assert new_db_row['version'] == '1.1.0'

        for attr in ['description', 'module_details', 'owner',
                     'published_at', 'readme_content', 'repo_base_url_template',
                     'repo_browse_url_template', 'repo_clone_url_template',
                     'variable_template']:
            assert new_db_row[attr] == None

        # Ensure that all moduleversion, submodules and example files have been removed
        with db.get_engine().connect() as conn:
            mv_res = conn.execute(db.module_version.select(
                db.module_version.c.id == 10001
            ))
            assert [r for r in mv_res] == []

            # Check for any submodules with the original IDs
            # or with the previous module ID or with the example
            # paths
            sub_module_res = conn.execute(db.sub_module.select().where(
                sqlalchemy.or_(
                    db.sub_module.c.id.in_((10002, 10003)),
                    db.sub_module.c.parent_module_version == 10001,
                    db.sub_module.c.path.in_(('example/test-modal-db-row-create-here',
                                              'modules/test-modal-db-row-create-there'))
                )
            ))
            assert [r for r in sub_module_res] == []

            # Ensure example files have been removed
            example_file_res = conn.execute(db.example_file.select().where(
                db.example_file.c.id == 10004
            ))
            assert [r for r in example_file_res] == []


    @pytest.mark.parametrize('template,version,expected_string', [
        ('= {major}.{minor}.{patch}', '1.5.0', '= 1.5.0'),
        ('<= {major_plus_one}.{minor_plus_one}.{patch_plus_one}', '1.5.0', '<= 2.6.1'),
        ('>= {major_minus_one}.{minor_minus_one}.{patch_minus_one}', '4.3.2', '>= 3.2.1'),
        ('>= {major_minus_one}.{minor_minus_one}.{patch_minus_one}', '0.0.0', '>= 0.0.0'),
        ('< {major_plus_one}.0.0', '10584.321.564', '< 10585.0.0'),
        # Test that beta version returns the version and
        # ignores the version template
        ('>= {major_minus_one}.{minor_minus_one}.{patch_minus_one}', '5.6.23-beta', '5.6.23-beta')
    ])
    def test_get_terraform_example_version_string(self, template, version, expected_string):
        """Test get_terraform_example_version_string method"""
        with unittest.mock.patch('terrareg.config.Config.TERRAFORM_EXAMPLE_VERSION_TEMPLATE', template):
            namespace = Namespace(name='test')
            module = Module(namespace=namespace, name='test')
            module_provider = ModuleProvider.get(module=module, name='test', create=True)
            module_version = ModuleVersion(module_provider=module_provider, version=version)
            module_version.prepare_module()
            assert module_version.get_terraform_example_version_string() == expected_string
