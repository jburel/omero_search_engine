import os
from omero_search_engine import search_omero_app
from flask_script import Manager
from configurations.configuration import update_config_file
from omero_search_engine.cache_functions.elasticsearch.transform_data import (
    create_omero_indexes,
    delte_data_from_index,
    delete_index,
    get_insert_data_to_index,
    get_all_indexes,
    insert_resource_data,
    save_key_value_buckets
)

from omero_search_engine.cache_functions.elasticsearch.sql_to_csv import (
    sqls_resources,
)

from omero_search_engine.validation.results_validator import (
    validate_queries,
    test_no_images,
    get_omero_stats,
)

manager = Manager(search_omero_app)


@manager.command
def show_saved_indices():
    all_indexes = get_all_indexes()
    for index in all_indexes:
        print("Index: ==>>>", index)
    # return (all_indexes)


@manager.command
@manager.option(
    "-r",
    "--resource",
    help="resource name, deleting all the indexes for all the resources is the default", # noqa
)
@manager.option(
    "-e",
    "--es_index",
    help="elastic index name, if it is provided, it will delete and return",
)
def delete_es_index(resource="all", es_index=None):
    delete_index(resource, es_index)


@manager.command
@manager.option(
    "-r",
    "--resource",
    help="resource name, deleting all data from the its related index",
)
def delete_all_data_from_es_index(resource="None"):
    delte_data_from_index(resource)


@manager.command
@manager.option("-r", "--resource", help="resource name, e.g. image")
@manager.option("-d", "--data_folder", help="Folder contains the data files")
@manager.option("-f", "--from_json", help="Folder contains the data files")
def add_resource_data_to_es_index(resource=None, data_folder=None,
                                  from_json=False):
    """=
    Insert data inside elastic search index by getting the data from csv files
    """
    if not resource or not data_folder or not os.path.exists(data_folder):
        search_omero_app.logger.info(
            "Please check the input parameters, resource:\
            {resource}, data_folder: {data_folder}".format(
                resource=resource, data_folder=data_folder
            )
        )
        return
    insert_resource_data(data_folder, resource, from_json)


@manager.command
@manager.option(
    "-r",
    "--resource",
    help="resource name, creating all the indcese for all the resources is the default", # noqa
)
def create_index(resource="all"):
    """
    Create Elasticsearch index for each resource
    """
    create_omero_indexes(resource)


def sql_results_to_panda():
    pass


@manager.command
@manager.option(
    "-r",
    "--resource",
    help="resource name, creating all the indcese for all the resources is the default", # noqa
)
def get_index_data_from_database(resource="all"):
    """
    insert data in Elasticsearch index for each resource
    It gets the data from postgres database server
    """
    if resource != "all":
        sql_st = sqls_resources.get(resource)
        if not sql_st:
            return
        get_insert_data_to_index(sql_st, resource)
    else:
        for res, sql_st in sqls_resources.items():
            get_insert_data_to_index(sql_st, res)
        save_key_value_buckets(
            resource_table_=None, re_create_index=True, only_values=False
        )
        # validat ethe indexing
        test_indexing_search_query(deep_check=True, check_studies=True)


# set configurations
@manager.command
@manager.option("-u", "--url", help="database server url")
@manager.option("-s", "--server_port_number", help="database port number")
@manager.option("-d", "--database", help="database name")
@manager.option("-n", "--name", help="database usernname")
@manager.option("-p", "--password", help="database username password")
def set_database_configuration(
    url=None, server_port_number=None, database=None, name=None, password=None
):
    database_attrs = {}
    if url:
        database_attrs["DATABASE_SERVER_URI"] = url
    if database:
        database_attrs["DATABASE_NAME"] = database
    if name:
        database_attrs["DATABASE_USER"] = name
    if password:
        database_attrs["DATABASE_PASSWORD"] = password
    if server_port_number and server_port_number.isdigit():
        database_attrs["DATABASE_PORT"] = server_port_number

    if len(database_attrs) > 0:
        update_config_file(database_attrs)
    else:
        search_omero_app.logger.info(
            "At least one database attributed\
             (i.e. url, database name, username, username password)\
             should be provided"
        )


@manager.command
@manager.option("-e", "--elasticsearch_url", help="elasticsearch url")
def set_elasticsearch_configuration(elasticsearch_url=None):
    if elasticsearch_url:
        update_config_file({"ELASTICSEARCH_URL": elasticsearch_url})
    else:
        search_omero_app.logger.info("No attribute is provided")


@manager.command
@manager.option("-c", "--cache_folder", help="cache folder path")
def set_cache_folder(cache_folder=None):
    if cache_folder:
        update_config_file({"CACHE_FOLDER": cache_folder})
    else:
        search_omero_app.logger.info("No attribute is provided")


@manager.command
@manager.option("-i", "--idr_url", help="URL for idr test file")
def set_idr_test_file(idr_url=None):
    if idr_url:
        update_config_file({"IDR_TEST_FILE_URL": idr_url})
    else:
        search_omero_app.logger.info("No attribute is provided")


@manager.command
@manager.option("-n", "--number_cache_rows", help="cache folder path")
def set_cache_rows_number(number_cache_rows=None):
    if number_cache_rows and number_cache_rows.isdigit():
        update_config_file({"CACHE_ROWS": int(number_cache_rows)})
    else:
        search_omero_app.logger.info("No of cached rows has to be an integer")


@manager.command
@manager.option("-s", "--secret_key", help="cache folder path")
def set_searchengine_secret_key(secret_key=None):
    if secret_key:
        update_config_file({"SECRET_KEY": secret_key})
    else:
        search_omero_app.logger.info("No value is provided")


@manager.command
@manager.option("-s", "--page_size", help="Page size")
def set_max_page(page_size=None):
    if page_size and page_size.isdigit():
        update_config_file({"PAGE_SIZE": int(page_size)})
    else:
        search_omero_app.logger.info("No valid attribute is provided")


@manager.command
@manager.option("-n", "--no_processes", help="no_processes")
def set_no_processes(no_processes=None):
    if no_processes and no_processes.isdigit():
        update_config_file({"NO_PROCESSES": int(no_processes)})
    else:
        search_omero_app.logger.info("No valid attribute is provided")


@manager.command
@manager.option(
    "-r",
    "--resource",
    help="resource name, creating all the indexes for all the resources is the default", # noqa
)
@manager.option(
    "-c", "--create_index", help="creating the elastic search index if set to True" # noqa
)
@manager.option("-o", "--only_values", help="creating cached values only ")
def cache_key_value_index(resource=None, create_index=None, only_values=None):
    """
    Cache the value bucket for each value for each resource
    """
    save_key_value_buckets(resource, create_index, only_values)


@manager.command
@manager.option("-j", "--json_file", help="creating cached values only ")
@manager.option("-c", "--check_studies", help="check studies from idr ")
@manager.option(
    "-d",
    "--deep_check",
    help="compare all the images from both search engine and database server, default is False so it will compare the number of images and the first searchengine page", # noqa
)
def test_indexing_search_query(
    json_file="app_data/test_index_data.json", deep_check=False,
    check_studies=False
):
    """
    test the indexing and the searchengine query functions
    can be used:
      * after the indexing to check the elasticsearch index data
      * after the code modifications to check the searchengine queries results
    The test data can be provided from and external files,
    i.e. json file format
    if the data file, it will use sample file from
    (test_index_data.json) app_data folder
    """

    validate_queries(json_file, deep_check)
    if check_studies:
        test_no_images()
    get_omero_stats()


if __name__ == "__main__":
    manager.run()
