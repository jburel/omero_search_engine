import requests
import json
import sys

# url to send the query
IMAGE_SEARCH = "searchannotation/"
# url to get the next page for a query, bookmark is needed
IMAGE_PAGE_SEARCH = "searchannotation_page/"

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


def main(file):

    # Load the values to test
    entries, url = load_configuration_file(file);
    # Run the various queries
    for entry in entries:
        received_results = []
        ids = []
        page = 1
        key = entry["field"]
        value = entry["term"]
        # number of expected images
        expected_images = entry["images"]
        expected_containers = entry["containers"]
            
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
        search_url = url + IMAGE_SEARCH
        bookmark, total_pages, results = load_results(search_url, data=query_data_json)
        # Check for duplicate
        for r in results:
            if r['id'] not in ids:
                ids.append(r["id"])
            received_results.append(r)
        screens_ids = []
        project_ids = []
        search_page_url = url + IMAGE_PAGE_SEARCH
        while page < total_pages:
            page += 1
            # add bookmark to the query, so it will return the next page
            query_data_ = {"query": {"query_details": {"and_filters": and_filters}},
                           "bookmark": bookmark}
            query_data_json_ = json.dumps(query_data_)
            # call the server
            bookmark, pages, results = load_results(search_page_url, data=query_data_json_)

            for r in results:
                if r['id'] not in ids:
                    ids.append(r["id"])
                    received_results.append(r)
        total_images = 0
        for image in received_results:
            parent_id = image['project_id']
            if image['project_id'] is None and image['screen_id'] is None:
                print(image['id'])

            if parent_id is not None:
                if parent_id not in project_ids:
                    project_ids.append(parent_id)
                if parent_id != 2101:
                	total_images += 1
            else:
                parent_id = image['screen_id']
                if parent_id is not None:
                    if parent_id not in screens_ids:
                       screens_ids.append(parent_id)
                    total_images += 1

        total = len(screens_ids) + len(project_ids)
        n = len(received_results)
        print(total_images)
        print(f"{key}: {value}, number of images found: {n}, expected: {expected_images}. Number of experiments/screens found: {total}, expected: {expected_containers}")


if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description="Extract information from input file")
    parser.add_argument("file", nargs='?', default="data.json")
    args = parser.parse_args()
    main(args.file)
