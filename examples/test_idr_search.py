import requests
import json
import sys

# url to send the query
IMAGE_SEARCH = "image/searchannotation/?data_source={data_source}"
# url to get the next page for a query, bookmark is needed
IMAGE_PAGE_SEARCH = "image/searchannotation_page/?data_source={data_source}"

# url to load the cached data
KEY_VALUE_SEARCH = "image/searchvaluesusingkey/?key={key}&data_source={data_source}"

DATA_SOURCES = "data_sources/"

def load_data_sources(url):
    source_url = url + DATA_SOURCES
    response = requests.get(source_url)
    return json.loads(response.text)


def load_configuration_file(file):
    # Read the data to test and the expected results
    with open(file, 'r') as file:
        data = json.load(file)
        url = data["@url"]
        entries = data["@data"]
    return entries, url

def load_results(url, data=None, method="post"):
    if method == "post":
        resp = requests.post(url, data=data)
    else:
        resp = requests.get(url)
    try:
        returned_results = json.loads(resp.text)

        if returned_results.get("results") is None or len(returned_results["results"]) == 0:
            return None, 0, None

        
        # get the bookmark which will be used to call
        # the next page of the results
        bookmark = returned_results["results"]["bookmark"]

        # get the size of the total results
        total_results = returned_results["results"]["size"]
        results = returned_results["results"]["results"]
        total_pages = returned_results["results"]["total_pages"]
        return bookmark, total_pages, results
    except Exception as ex:
        print(ex)


def load_cached_results(url):
    try:
        resp = requests.get(url=url)
        returned_results = json.loads(resp.text)
        if returned_results.get("data") is None or len(returned_results["data"]) == 0:
            return None
        return returned_results.get("data")
    except Exception as ex:
        print(ex)


def load_cached_data(entries, url, sources):

    # Run the various queries
    for entry in entries:
        received_results = []
        ids = []
        page = 1
        key = entry["field"]
        value = entry["term"].strip()
        source = entry.get("data_source")
        if source is None:
            source = "idr"  # default to IDR for now Add endpoint to find the default

        # number of expected images
        expected_images = entry["images"]
        query = {'key': key}

        operator = entry.get("operator")
        if operator is None:
            operator = "equals"
        if source is None:
            source = "idr"  # default to IDR for now Add endpoint to find the default
        query.update({'data_source': source}) 
        search_url = url + KEY_VALUE_SEARCH.format(**query)
        results = load_cached_results(search_url)
        if results is None:
            print(f"{key}: {value}. No results found in source {source}")
        else:
            n = 0
            for result in results:
                if operator == "contains":
                    if value in result['Value']:
                        n += result['Number of images']
                elif operator == "equals":
                    if value == result['Value']:
                        n += result['Number of images']
            print(f"{key}: {value}, number of images found: {n}, expected: {expected_images}, source found: {result['data_source']}, expected: {source}")


def load_non_cached_data(entries, url, sources):

    # Run the various queries
    for entry in entries:
       
        source = entry.get("data_source")
        if source is None:
            source = "idr"  # default to IDR for now Add endpoint to find the default
        if source not in sources:
            print(f"Datasource {source} not supported")
            continue

        received_results = []
        ids = []
        page = 1
        key = entry["field"]
        value = entry["term"].strip()
        for_cached_call = entry.get("for_cached_call")
        if for_cached_call is None:
            for_cached_call = False
        if for_cached_call is True:
            print(f"skipping searching for {key}:{value} in source {source}")
            continue

        # number of expected images
        expected_images = entry["images"]
        expected_containers = entry.get("containers")
            
        #results = load_using_search_api(session, key, [value])
        # if operator is not set. operator is "equals"
        operator = entry.get("operator")
        if operator is None:
            operator = "equals"
        and_filters = [ {
            "name": key,
            "value": value,
            "operator": operator,
            "resource": "image",
            }]
        query_data = {"query_details": {"and_filters": and_filters}}
        
        query_data_json = json.dumps(query_data)
        query = {'data_source': source}
        search_url = url + IMAGE_SEARCH.format(**query)
        bookmark, total_pages, results = load_results(search_url, data=query_data_json)
        # Check for duplicate
        if results is not None:
            for r in results:
                if r['id'] not in ids:
                    ids.append(r["id"])
                received_results.append(r)
        screens_ids = []
        project_ids = []
        search_page_url = url + IMAGE_PAGE_SEARCH.format(**query)
        while page < total_pages:
            page += 1
            # add bookmark to the query, so it will return the next page
            query_data_ = {"query": {"query_details": {"and_filters": and_filters}},
                           "bookmark": bookmark}
            query_data_json_ = json.dumps(query_data_)
            # call the server
            bookmark, pages, results = load_results(search_page_url, data=query_data_json_)

            if results is not None:
                for r in results:
                    if r['id'] not in ids:
                        ids.append(r["id"])
                    received_results.append(r)
        for image in received_results:
            parent_id = image['project_id']
            if image['project_id'] is None and image['screen_id'] is None:
                print(image['id'])

            if parent_id is not None:
                if parent_id not in project_ids:
                    project_ids.append(parent_id)
            else:
                parent_id = image['screen_id']
                if parent_id is not None:
                    if parent_id not in screens_ids:
                       screens_ids.append(parent_id)

        total = len(screens_ids) + len(project_ids)
        n = len(received_results)
        print(f"{key}: {value}, number of images found: {n}, expected: {expected_images}. Number of experiments/screens found: {total}, expected: {expected_containers}, source: {source}")



def main(file, cached_data):

    # Load the values to test
    entries, url = load_configuration_file(file);

    # Check if the datasource is registered
    sources = load_data_sources(url)
    if cached_data == 'True':
        load_cached_data(entries, url, sources)
    else:
        load_non_cached_data(entries, url, sources)


if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description="Extract information from input file")
    parser.add_argument("-f", "--file", default="data.json")
    parser.add_argument("-c", "--cached", default="False")
    args = parser.parse_args()
    main(args.file, args.cached)
