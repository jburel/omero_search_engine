#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2022 University of Dundee & Open Microscopy Environment.
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from string import Template
from omero_search_engine import search_omero_app
import time
import json
import os
from omero_search_engine.api.v1.resources.utils import (
    resource_elasticsearchindex,
    build_error_message,
    adjust_value,
)
import math

key_number_search_template = Template(
    """
{"size":0,"aggs":{"value_search":{"nested":{"path":"key_values"},
"aggs":{"value_filter":{"filter":{"terms":
{"key_values.name.keyword":["$key"]}},
"aggs":{"required_values":{"cardinality":
{"field":"key_values.value.keyvalue","precision_threshold":4000
}}}}}}}}"""
)

search_by_value_only = Template(
    """
{"query":{"bool":{"must":[{"nested":
{"path":"key_values","query":{"bool":{"must":[{"wildcard":
{"key_values.value.keyvaluenormalize":"*eLa*"}}]}}}}]}}}"""
)

value_number_search_template = Template(
    """
{"size": 0,"aggs": {"name_search": {"nested":
{"path": "key_values"},"aggs": {"value_filter": {"filter": {
"terms": {"key_values.value.keyvaluenormalize":
["$value"]}},"aggs": {"required_name": {"cardinality": {
"field": "key_values.name.keyword","precision_threshold": 4000}}}}}}}}"""
)

value_search_template = Template(
    """
{"size": 0,"aggs": {"name_search":
{"nested": {"path": "key_values"},"aggs": {"value_filter": {
"filter": {"terms": {"key_values.value.keyvaluenormalize":
["$value"]}},"aggs": {"required_name": {
"terms": {"field": "key_values.name.keyword","size": 9999}}}}}}}}"""
)

value_search_contain_template = Template(
    """
{"size": 0,"aggs": {"name_search": {"nested": {"path": "key_values"},
"aggs": {"value_filter": {"terms":
{"field":"key_values.value.keyvaluenormalize","include": ".*$value.*"},
"aggs": {"required_name": {"terms":
{"field": "key_values.name.keyword","size": 9999}}}}}}}}"""
)

key_search_template = Template(
    """
{"size": 0,"aggs": {"name_search": {"nested": {"path": "key_values"},
"aggs": {"value_filter": {
"filter": {"terms": {"key_values.name.keyword": ["$key"]}},
"aggs": {"required_values": {
"terms": {"field": "key_values.value.keyvaluenormalize",
"size": 9999}}}}}}}}"""
)

values_for_key_template = Template(
    """
{"size":0,
"aggs":{"name_search":{"nested":{ "path":"key_values"},
"aggs":{"value_filter":{"filter":{
"terms":{"key_values.name.keyword":["$key"]}},"aggs":{"required_values":{
"terms":{"field":"key_values.value.keyvaluenormalize",
"include": {"partition": "$cur","num_partitions": "$total"},
"size":10000 }}}}}}}}"""
)


def search_index_for_value(e_index, query, get_size=False):
    """
    Perform search the elastcisearch using value and
    return all the key values whihch this value has been used,
    it will include the number of records.
    It is relatively slow but it might be due
    to the elasticsearcg hosting machine
    """
    es = search_omero_app.config.get("es_connector")
    if get_size:
        return es.count(index=e_index, body=query)
    res = es.search(index=e_index, body=query)
    return res


def search_index_for_values_get_all_buckets(e_index, query):
    """
    Perform search the elastcisearch using value and
    return all the key values whihch this value has been used,
    it will include the number of records.
    It is relatively slow but it might be due
    to the elasticsearcg hosting machine
    """
    page_size = 9999
    bookmark = 0
    query = json.loads(query)
    returened_results = []
    # es = search_omero_app.config.get("es_connector")
    res = connect_elasticsearch(e_index, query, True)
    # res = es.count(index=e_index, body=query)
    size = res["count"]
    query["size"] = page_size
    query["sort"] = [
        {
            "_script": {
                "script": "doc['Value.keyvaluenormalize'].value.length()",
                "type": "number",
                "order": "asc",
            }
        },
        {"items_in_the_bucket": "desc"},
        {"id": "asc"},
    ]
    co = 0
    while co < size:
        if co != 0:
            query["search_after"] = bookmark
        query["size"] = page_size
        res = connect_elasticsearch(
            e_index, query
        )  # es.search(index=e_index, body=query)
        returened_results.append(res)
        co += page_size
        if len(res["hits"]["hits"]) == 0:
            search_omero_app.logger.info(
                "No result is found in the final\
                loop: %s for size %s"
                % (co, size)
            )
            return returened_results
        bookmark = [
            int(res["hits"]["hits"][-1]["sort"][0]),
            int(res["hits"]["hits"][-1]["sort"][1]),
            res["hits"]["hits"][-1]["sort"][2],
        ]
    return returened_results


def search_value_for_resource_(table_, value):
    """
    send the request to elasticsearch and format the results
    """
    res_index = resource_elasticsearchindex.get(table_)
    query = value_search_contain_template.substitute(value=value.lower())
    res = search_index_for_value(res_index, query)
    total_number = 0
    returned_results = []
    if res.get("aggregations"):
        for bucket in (
            res.get("aggregations")
            .get("name_search")
            .get("value_filter")
            .get("buckets")
        ):
            value = bucket.get("key")
            for buc in bucket.get("required_name").get("buckets"):
                singe_row = {}
                returned_results.append((singe_row))
                key = buc.get("key")
                key_no = buc.get("doc_count")
                singe_row["Key"] = key
                singe_row["Value"] = value
                singe_row["Number of %ss" % table_] = key_no
                total_number += key_no
    return {"data": returned_results, "total_number": total_number}


def get_number_of_buckets(key, res_index):
    query = key_number_search_template.substitute(key=key)
    res = search_index_for_value(res_index, query)
    number_of_buckets = (
        res.get("aggregations")
        .get("value_search")
        .get("value_filter")
        .get("required_values")
        .get("value")
    )
    number_of_images = (
        res.get("aggregations").get("value_search").get("value_filter").get("doc_count")
    )
    # print (number_of_buckets, number_of_images)
    return number_of_buckets, number_of_images


def get_all_values_for_a_key(table_, key):
    res_index = resource_elasticsearchindex.get(table_)
    query = key_number_search_template.substitute(key=key)
    res = search_index_for_value(res_index, query)
    number_of_buckets = (
        res.get("aggregations")
        .get("value_search")
        .get("value_filter")
        .get("required_values")
        .get("value")
    )
    number_of_items = (
        res.get("aggregations").get("value_search").get("value_filter").get("doc_count")
    )

    total = math.ceil(number_of_buckets / 10000)

    co = 0
    results = []
    total_ret = 0
    while co < total:
        search_omero_app.logger.info("processing: %s / %s" % ((co + 1), total))
        query = values_for_key_template.substitute(key=key, total=total, cur=co)
        res = search_index_for_value(res_index, query)
        results.append(res)
        total_ret += len(
            res["aggregations"]["name_search"]["value_filter"]["required_values"][
                "buckets"
            ]
        )
        co += 1
    returned_results = []
    total_number = 0
    for res in results:
        if res.get("aggregations"):
            for bucket in (
                res.get("aggregations")
                .get("name_search")
                .get("value_filter")
                .get("required_values")
                .get("buckets")
            ):
                value = bucket.get("key")
                value_no = bucket.get("doc_count")
                total_number += value_no
                singe_row = {}
                returned_results.append(singe_row)
                singe_row["Key"] = key
                singe_row["Value"] = value
                singe_row["Number of %ss" % table_] = value_no

    return {
        "data": returned_results,
        "total_number": total_number,
        "total_number_of_%s" % (table_): number_of_items,
        "total_number_of_buckets": len(returned_results),
    }


def get_values_for_a_key(table_, key):
    """
    search the index to get the available values for a key
    and get values number for the key
    """
    total_number = 0
    res_index = resource_elasticsearchindex.get(table_)
    number_of_buckets, number_of_images = get_number_of_buckets(key, res_index)
    query = key_search_template.substitute(key=key)
    start_time = time.time()
    res = search_index_for_value(res_index, query)
    query_time = "%.2f" % (time.time() - start_time)
    print("TIME ...", query_time)
    returned_results = []
    if res.get("aggregations"):
        for bucket in (
            res.get("aggregations")
            .get("name_search")
            .get("value_filter")
            .get("required_values")
            .get("buckets")
        ):
            value = bucket.get("key")
            value_no = bucket.get("doc_count")
            total_number += value_no
            singe_row = {}
            returned_results.append(singe_row)
            singe_row["Key"] = key
            singe_row["Value"] = value
            singe_row["Number of %ss" % table_] = value_no
    return {
        "data": returned_results,
        "total_number": total_number,
        "total_number_of_%s" % (table_): number_of_images,
        "total_number_of_buckets": number_of_buckets,
    }


def prepare_search_results(results, size=0):
    returned_results = []
    total_number = 0
    number_of_buckets = 0
    resource = None
    for hit in results["hits"]["hits"]:
        res = hit["_source"]
        resource = res.get("resource")
        # ignore organism key in the results
        # please see (https://github.com/ome/omero_search_engine/issues/45)
        # This will be checked later.
        if (
            resource == "image"
            and res["Attribute"]
            and res["Attribute"].lower() == "organism"
        ):
            continue
        row = {}
        returned_results.append(row)
        row["Key"] = res["Attribute"]
        row["Value"] = res["Value"]
        row["Number of %ss" % resource] = res.get("items_in_the_bucket")
        total_number += res["items_in_the_bucket"]
        number_of_buckets += 1

    results_dict = {
        "data": returned_results,
        "total_number_of_%s" % (resource): total_number,
        "total_number_of_buckets": number_of_buckets,
    }
    if size > 0:
        results_dict["total_number_of_all_buckets"] = size
        if number_of_buckets < size:
            # this should be later to get the next page
            if len(results["hits"]["hits"]) > 0:
                results_dict["bookmark"] = [
                    int(results["hits"]["hits"][-1]["sort"][0]),
                    int(results["hits"]["hits"][-1]["sort"][1]),
                    results["hits"]["hits"][-1]["sort"][2],
                ]
            else:
                results_dict["bookmark"] = None
    return results_dict


def prepare_search_results_buckets(results_):
    returned_results = []
    total_number = 0
    number_of_buckets = 0
    resource = None
    for results in results_:
        for hit in results["hits"]["hits"]:
            row = {}
            returned_results.append(row)
            res = hit["_source"]
            row["Key"] = res["Attribute"]
            row["Value"] = res["Value"]
            resource = res.get("resource")
            row["Number of %ss" % resource] = res.get("items_in_the_bucket")
            total_number += res["items_in_the_bucket"]
            number_of_buckets += 1
    return {
        "data": returned_results,
        "total_number_of_%s" % (resource): total_number,
        "total_number_of_buckets": number_of_buckets,
    }


def get_key_values_return_contents(name, resource, csv):
    from flask import jsonify, Response

    resource_keys = query_cashed_bucket(name, resource)
    # if a csv flag is true thenm iut will send a CSV file
    # which contains the results otherwise it will return a JSON file
    if csv:
        if resource != "all":
            content = ""
            d = resource_keys.get("data")
            if d and len(d) > 0:
                key_string = ",".join(d[0].keys())
                st = ""
                for e in d:
                    v = '","'.join(str(sr) for sr in e.values())
                    st = st + '\n" %s"' % v
                content = key_string + st

        else:
            key_string = ""
            content = []
            for resource_, data in resource_keys.items():
                d = data.get("data")
                if d and len(d) > 0:
                    if not key_string:
                        key_string = "resource," + ",".join(d[0].keys())
                    for e in d:
                        content.append(
                            "%s," % resource_
                            + '"%s"' % (('","'.join(str(sr) for sr in e.values())))
                        )

            content = key_string + "\n" + "\n".join(content)
        if content and len(content) > 0:
            return Response(
                content,
                mimetype="text/csv",
                headers={
                    "Content-disposition": "attachment; filename=%s_%s.csv"
                    % (name.replace(" ", "_"), resource)
                },
            )

    return jsonify(resource_keys)


def query_cashed_bucket_part_value_keys(
    name, value, resource, es_index="key_value_buckets_information"
):
    """
    Search for and obtain the available values for an attribute and part of the
    value for one or all resources
    e.g. 'homo' to return all values which contain 'homo'
    for the provided attribute and resource.

    """
    if name:
        name = name.strip()
    value = adjust_value(value)
    if resource != "all":
        query = key_part_values_buckets_template.substitute(
            name=name, value=value, resource=resource
        )
        res = search_index_for_values_get_all_buckets(es_index, query)
        returned_results = prepare_search_results_buckets(res)
        return returned_results
    else:
        # search all resources for all possible matches
        returned_results = {}
        for table in resource_elasticsearchindex:
            query = key_part_values_buckets_template.substitute(
                name=name, value=value, resource=table
            )
            res = search_index_for_values_get_all_buckets(es_index, query)
            returned_results[table] = prepare_search_results_buckets(res)
        return returned_results


def query_cashed_bucket(name, resource, es_index="key_value_buckets_information"):
    # returns possible matches for a specific resource
    if name:
        name = name.strip()
    if resource != "all":
        query = key_values_buckets_template.substitute(name=name, resource=resource)
        res = search_index_for_values_get_all_buckets(es_index, query)
        returned_results = prepare_search_results_buckets(res)
        return returned_results
    else:
        # search all resources for all possible matches
        returned_results = {}
        for table in resource_elasticsearchindex:
            query = key_values_buckets_template.substitute(name=name, resource=table)
            res = search_index_for_values_get_all_buckets(es_index, query)
            returned_results[table] = prepare_search_results_buckets(res)
        return returned_results


def query_cashed_bucket_value(value, es_index="key_value_buckets_information"):
    query = value_all_buckets_template.substitute(value=value)
    res = search_index_for_value(es_index, query)
    return prepare_search_results(res)


def search_value_for_resource(
    table_, value, bookmarks=None, es_index="key_value_buckets_information"
):
    """
    send the request to elasticsearch and format the results
    It support wildcard operations only
    """
    value = adjust_value(value)

    if table_ != "all":
        query = resource_key_values_buckets_template.substitute(
            value=value, resource=table_
        )
        size_query = resource_key_values_buckets_size_template.substitute(
            value=value, resource=table_
        )
        # Get the total number of the results.
        res = search_index_for_value(es_index, size_query, True)
        size = res["count"]
        # use bookmark is it is provided
        if bookmarks:
            query = json.loads(query)
            query["search_after"] = bookmarks

        res = search_index_for_value(es_index, query)
        return prepare_search_results(res, size)
    else:
        returned_results = {}
        for table in resource_elasticsearchindex:
            # ignore image1 as it is used for testing
            if table == "image1":
                continue
            # res = es.count(index=e_index, body=query)
            query = resource_key_values_buckets_template.substitute(
                value=value, resource=table
            )
            size_query = resource_key_values_buckets_size_template.substitute(
                value=value, resource=table_
            )
            # Get the total number of the results.
            res = search_index_for_value(es_index, size_query, True)
            size = res["count"]
            res = search_index_for_value(es_index, query)
            returned_results[table] = prepare_search_results(res, size)
        return returned_results


"""
Search using key and resource
"""
key_values_buckets_template = Template(
    """
{"query":{"bool":{"must":[{"bool":{
"must":{"match":{"Attribute.keyrnamenormalize":"$name"}}}},{
"bool": {"must": {"match":
{"resource.keyresource": "$resource"}}}}]}}}"""
)

"""
Search using key, part of the value and resource
"""
key_part_values_buckets_template = Template(
    """
{"query":{"bool":{"must":[{"bool":{
"must":[{"match":{"Attribute.keyrnamenormalize":"$name"}},
{"wildcard":{"Value.keyvaluenormalize":"*$value*"}}
]
}},{
"bool": {"must": [
{"match":{"resource.keyresource": "$resource"}}
]}}]}}}"""
)

# "fields": ["Attribute","Value","items_in_the_bucket",
# "total_items_in_saved_buckets","total_buckets","total_items"],
# "_source": false,
ss = Template(
    """
{"query":{"bool":{"must":[{"bool":{
"must":{"match":{"Attribute.keyname":"$name"}}}},{"bool": {
"must": {"match": {"resource.keyresource": "$resource"}}}}]}}
"size": 9999}"""
)

"""
Search using value and resource
"""
key_values_search_buckets_template = Template(
    """
{"query":{"bool":{"must":[{"bool":{
"must":{"match":{"Value.keyvalue":"$value"}}}},{
"bool": {"must": {"match":
{"resource.keyresource": "$resource"}}}}]}},"size": 9999}"""
)

"""
Search using value or part of value and return all the posible mathes
"""

value_all_buckets_template = Template(
    """
{"query":{"bool":{"must":[{"bool":{
"must":{"wildcard":
{"Value.keyvaluenormalize":"*$value*"}}}}]}},"size": 9999}"""
)

resource_key_values_buckets_size_template = Template(
    """
{"query":{"bool":{"must":[{"bool":{
"must":{"wildcard":{"Value.keyvaluenormalize":"*$value*"}}}},{
"bool": {"must": {"match":
{"resource.keyresource": "$resource"}}}}]}}}"""
)

resource_key_values_buckets_template = Template(
    """
{"query":{"bool":{"must":[{"bool":{
"must":{"wildcard":{"Value.keyvaluenormalize":"*$value*"}}}},{
"bool": {"must": {"match":
{"resource.keyresource": "$resource"}}}}]}},
"size": 9999, "sort":[{ "_script": {
        "script": "doc['Value.keyvaluenormalize'].value.length()",
        "type": "number",
        "order": "asc"
    }},{"items_in_the_bucket": "desc"}, {"id": "asc"}]}"""
)

key_values_buckets_template_2 = Template(
    """
{"query":{"bool":{"must":[{"bool":{"must":{"match":{
"resource.keyresource":"$resource"}}}}]}}} """
)


def connect_elasticsearch(es_index, query, count=False):
    es = search_omero_app.config.get("es_connector")
    # test the elasticsearch connection
    if not es.ping():
        raise ValueError("Elasticsearch connection failed")
    if not count:
        return es.search(index=es_index, body=query)
    else:
        return es.count(index=es_index, body=query)


def get_restircted_search_terms():
    search_terms = (
        "omero_search_engine/api/v1/resources/data/restricted_search_terms.json"  # noqa
    )

    if not os.path.isfile(search_terms):
        return {}
    with open(search_terms) as json_file:
        restricted_search_terms = json.load(json_file)
    return restricted_search_terms


def get_resource_attributes(resource, mode=None, es_index="key_values_resource_cach"):
    """
    return the available attributes for one or all resources
    """
    if mode and mode != "searchterms":
        return build_error_message(
            "The mode parameter supports only 'searchterms'\
            to return the common search terms,\
            you may remove it to return all the keys."
        )
    returned_results = {}
    if resource != "all":
        query = key_values_buckets_template_2.substitute(resource=resource)
        res = connect_elasticsearch(
            es_index, query
        )  # es.search(index=es_index, body=query)
        hits = res["hits"]["hits"]
        if len(hits) > 0:
            returned_results[resource] = hits[0]["_source"]["name"]
    else:
        for table in resource_elasticsearchindex:
            query = key_values_buckets_template_2.substitute(resource=table)
            res = connect_elasticsearch(
                es_index, query
            )  # .search(index=es_index, body=query)
            hits = res["hits"]["hits"]
            if len(hits) > 0:
                returned_results[table] = hits[0]["_source"]["name"]

    if mode == "searchterms":
        restricted_search_terms = get_restircted_search_terms()
        restircted_resources = {}
        for k, val in returned_results.items():
            if k in restricted_search_terms:
                search_terms = list(set(restricted_search_terms[k]) & set(val))
                if len(search_terms) > 0:
                    restircted_resources[k] = search_terms
        returned_results = restircted_resources
        if "project" in returned_results:
            returned_results["project"].append("Name (IDR number)")

    return returned_results


attribute_search_values_template = Template(
    """
{"query":{"bool":{"must":[
{"bool":{"must":{"match":{"resource.keyresource":"$resource"}}}},
{"bool": {"must":
{"match": {"Attribute.keyname":"$name"}}}}]}},"size":9999}"""
)


def get_resource_attribute_search_values(
    resource, name, value="", es_index="key_value_buckets_information"
):
    """
    Search values for a resource attribute,
    It can be used for autocomplete, to work like any attribute
    """
    returned_results = []
    query = attribute_search_values_template.substitute(
        resource=resource, name=name
    )  # , value=value)
    results = search_index_for_value(es_index, query, value=value)
    if len(results["hits"]["hits"]) > 0:
        for res in results["hits"]["hits"]:
            row = {}
            returned_results.append(row)
            row["value"] = res["_source"]["Value"]
            row["Number of %ss" % resource] = res["_source"][
                "items_in_the_bucket"
            ]  # noqa
    return returned_results


def get_resource_attribute_values(
    resource, name, es_index="key_value_buckets_information"
):
    """
    return values for a resource attribute
    """
    returned_results = []
    try:
        query = key_values_buckets_template.substitute(name=name, resource=resource)
        results_ = search_index_for_values_get_all_buckets(es_index, query)
        for results in results_:
            for hit in results["hits"]["hits"]:
                res = hit["_source"]
                # row={}
                # row["Value"] = res["Value"]
                # items = res.get("items_in_the_bucket")
                # row["Number of %ss" % resource] = items
                returned_results.append(res["Value"])
    except Exception as e:
        search_omero_app.logger.info("Errro: %s" % str(e))

    return returned_results


def get_resource_names(resource, es_index="key_values_resource_cach"):
    """
    return resources names attributes
    It works for projects and screens but can be extended.
    """
    returned_results = []
    if resource != "all":
        query = key_values_buckets_template_2.substitute(resource=resource)
        results_ = connect_elasticsearch(
            es_index, query
        )  # .search(index=es_index, body=query)
        hits = results_["hits"]["hits"]
        if len(hits) > 0:
            returned_results = hits[0]["_source"]["resourcename"]
    else:
        ress = ["project", "screen"]
        for res in ress:
            query = key_values_buckets_template_2.substitute(resource=res)
            results_ = connect_elasticsearch(
                es_index, query
            )  # .search(index=es_index, body=query)
            if len(results_["hits"]["hits"]) > 0:
                returned_results = (
                    returned_results
                    + results_["hits"]["hits"][0]["_source"]["resourcename"]
                )
    return returned_results
