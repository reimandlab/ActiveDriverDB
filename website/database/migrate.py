import re
from warnings import warn

from database import db
from helpers.commands import got_permission


def add_column(engine, table_name, definition):
    sql = f'ALTER TABLE `{table_name}` ADD {definition}'
    engine.execute(sql)


def drop_column(engine, table_name, column_name):
    sql = f'ALTER TABLE `{table_name}` DROP `{column_name}`'
    engine.execute(sql)


def update_column(engine, table_name, column_definition):
    sql = f'ALTER TABLE `{table_name}` MODIFY COLUMN {column_definition}'
    engine.execute(sql)


def set_foreign_key_checks(engine, active=True):
    sql = f'SET FOREIGN_KEY_CHECKS={1 if active else 0};'
    if engine.dialect.name == 'sqlite':
        warn('Sqlite foreign key checks managements is not supported')
        return False
    engine.execute(sql)
    return True


def set_autocommit(engine, active=True):
    sql = f'SET AUTOCOMMIT={1 if active else 0};'
    if engine.dialect.name == 'sqlite':
        warn('Sqlite autocommit managements is not supported')
        return False
    engine.execute(sql)
    return True


def set_unique_checks(engine, active=True):
    sql = f'SET UNIQUE_CHECKS={1 if active else 0};'
    if engine.dialect.name == 'sqlite':
        warn('Sqlite unique key checks managements is not supported')
        return False
    engine.execute(sql)
    return True


def get_column_names(table):
    return set((i.name for i in table.c))


def basic_auto_migrate_relational_db(app, bind):
    """Inspired by http://stackoverflow.com/questions/2103274/"""

    from sqlalchemy import Table
    from sqlalchemy import MetaData

    print('Performing auto-migration in', bind, 'database...')
    db.session.commit(bind=bind)
    db.reflect(bind=bind)
    db.session.commit(bind=bind)
    db.create_all(bind=bind)

    with app.app_context():
        engine = db.get_engine(app, bind)
        tables = db.get_tables_for_bind(bind=bind)
        metadata = MetaData()
        metadata.engine = engine

        ddl = engine.dialect.ddl_compiler(engine.dialect, None)

        for table in tables:

            db_table = Table(
                table.name, metadata, autoload=True, autoload_with=engine
            )
            db_columns = get_column_names(db_table)

            columns = get_column_names(table)
            new_columns = columns - db_columns
            unused_columns = db_columns - columns
            existing_columns = columns.intersection(db_columns)

            for column_name in new_columns:
                column = getattr(table.c, column_name)
                if column.constraints:
                    print(f'Column {column_name} skipped due to existing constraints.')
                    continue
                print(f'Creating column: {column_name}')

                definition = ddl.get_column_specification(column)
                add_column(engine, table.name, definition)

            if engine.dialect.name == 'mysql':
                sql = f'SHOW CREATE TABLE `{table.name}`'
                table_definition = engine.execute(sql)
                columns_definitions = {}

                to_replace = {
                    'TINYINT(1)': 'BOOL',   # synonymous for MySQL and SQLAlchemy
                    'INT(11)': 'INTEGER',
                    'DOUBLE': 'FLOAT(53)',
                    ' DEFAULT NULL': ''
                }
                for definition in table_definition.first()[1].split('\n'):
                    match = re.match(r'\s*`(?P<name>.*?)` (?P<definition>[^,]*),?', definition)
                    if match:
                        name = match.group('name')
                        definition_string = match.group('definition').upper()

                        for mysql_explicit_definition, implicit_sqlalchemy in to_replace.items():
                            definition_string = definition_string.replace(mysql_explicit_definition, implicit_sqlalchemy)

                        columns_definitions[name] = name + ' ' + definition_string

                columns_to_update = []
                for column_name in existing_columns:

                    column = getattr(table.c, column_name)
                    old_definition = columns_definitions[column_name]
                    new_definition = ddl.get_column_specification(column)

                    if old_definition != new_definition:
                        columns_to_update.append([column_name, old_definition, new_definition])

                if columns_to_update:
                    print(
                        f'\nFollowing columns in `{table.name}` table differ in definitions '
                        f'from those specified in models: {columns_to_update}'
                    )
                for column, old_definition, new_definition in columns_to_update:
                    agreed = got_permission(
                        f'Column: `{column}`\n'
                        f'Old definition: {old_definition}\n'
                        f'New definition: {new_definition}\n'
                        'Update column definition?'
                    )
                    if agreed:
                        update_column(engine, table.name, new_definition)
                        print(f'Updated {column} column definition')
                    else:
                        print(f'Skipped {column} column')

            if unused_columns:
                print(
                    f'\nFollowing columns in `{table.name}` table are no longer used '
                    f'and can be safely removed: {unused_columns}'
                )
                for column in unused_columns:
                    if got_permission(f'Column: `{column}` - remove?'):
                        drop_column(engine, table.name, column)
                        print(f'Removed column {column}.')
                    else:
                        print(f'Keeping column {column}.')

    print('Auto-migration of', bind, 'database completed.')
