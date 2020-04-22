from django.http import Http404, HttpResponse
from django.shortcuts import render
from . import models
from elasticsearch import Elasticsearch

import json

ERR_QUERY_NOT_FOUND = '<h1>Query not found</h1>'
ERR_IMG_NOT_AVAILABLE = 'The requested result can not be shown now'

# USER = open("elastic-settings.txt").read().split("\n")[1]
# PASSWORD = open("elastic-settings.txt").read().split("\n")[2]
ELASTIC_INDEX = 'cord_meta'

# open connection to Elastic
es = Elasticsearch(['http://csxindex05:9200/'], verify_certs=True)

if not es.ping():
    raise ValueError("Connection failed")


def Home(request):
    return render(request, 'seer/index.html')


# Formats the list of authors with their metadata
def __get_author_list(result):

    author_list = []

    for data in result['_source']['metadata']['authors']:
        author = dict()

        # Build the name for the author
        first_name = data['first']
        mid_name = data['middle']

        if len(mid_name) > 0:
            first_name += " " + mid_name[0]

        last_name = data['last']
        suffix = data['suffix']

        author['name'] = ' '.join([first_name, last_name, suffix])

        if suffix is None or suffix == '':
            author['name'] = ' '.join([first_name, last_name])
            print(first_name)
        else:
            author['name'] = ' '.join([first_name, last_name, suffix])
            print("SUFFIX:", suffix)

        # Build the affiliation of the author
        if len(data['affiliation']) > 0:

            # Build the geographic location of the author
            if data['affiliation']['location']:
                location = data['affiliation']['location']

                location_list = list()

                if 'settlement' in location:
                    location_list.append(location['settlement'])
                if 'region' in location:
                    location_list.append(location['region'])
                if 'country' in location:
                    location_list.append(location['country'])

                author['location'] = ", ".join(location_list)
            else:
                author['location'] = 'N/A'

            author['institution'] = data['affiliation']['institution'] or 'N/A'
            author['laboratory'] = data['affiliation']['laboratory'] or 'N/A'
        else:
            author['location'] = 'N/A'
            author['institution'] = 'N/A'
            author['laboratory'] = 'N/A'

        print(author)
        author_list.append(author)

    return author_list


def __search(request, query, page):
    size = 15
    start = (page - 1) * size
    body = {
        "from": start,
        "size": size,
        "query": {
            "multi_match": {
                "query": query,
                "fields":  ["body_text","abstract", "metadata.title"],
            }

        },
        'highlight': {'fields': {'body_text': {}, 'abstract.text': {}}}
    }
    res = es.search(index=ELASTIC_INDEX, body=body)
    #print("RESULTS", res)
    #print("RESULTS keys", res['hits']['total']['value'])

    if not res.get('hits') or len(res) == 0 or res['hits']['total']['value'] == 0:
        return render(request, 'seer/results.html',
                      {'q': query, 'errormessage': 'Your query returned zero results, please try another query.'})
    else:
        print("search done")
        totalresultsNumFound = res['hits']['total']['value']
        # hlresults=r.json()['highlighting']
        results = res['hits']['hits']
        print('Got :',res['hits']['total']['value'])
        SearchResults = []
        if len(results) > 0:
            for result in results:
                resultid = result['_id']
                f = models.SearchResult(resultid)  # calling the object class that is defined inside models.py
                f.title = result['_source']['metadata']['title']

                if len(f.title) == 0:
                    continue

                f.content = result['_source']['body_text']
                if len(result['_source']['metadata']['authors'])>0:
                    if 'location' in result['_source']['metadata']['authors'][0]['affiliation']:
                        f.affiliation = result['_source']['metadata']['authors'][0]['affiliation']['location']
                else:
                    f.affiliation = ''
                # rawpath= result['_source']['file']['url']

                # removing local folder path
                f.url = result['_source']['metadata']['title']

                f.title = result['_source']['metadata']['title']
                f.authors = __get_author_list(result)

                # f.description = str(result['_source']['meta']['raw']['description'])
                f.description = ''
                if 'highlight' in result:
                    if 'body_text' in result['highlight']:
                        for desc in result['highlight']['body_text']:
                            f.description = f.description + desc + '\n'

                # f.description = " ".join(f.description).encode("utf-8")
                '''
                if len(result.get('category',[])) > 0:
                   f.category=result['category'][0].encode("utf-8") 
                '''
                # trying to use the location field to get the file name to display the image
                # f.filename= str(imageid)+'.png'
                f.doi = result['_source']['doi']
                f.source = result['_source']['source_x']
                f.journal = result['_source']['journal']
                
                SearchResults.append(f)

            context = dict()
            context['results'] = SearchResults
            context['q'] = query
            context['total'] = totalresultsNumFound
            context['pageSize'] = size
            context['position'] = start + 1
            context['nextResults'] = len(results) + start
            context['prevResults'] = start - size

            context['page'] = (context['position'] // size) + 1
            context['nextPage'] = max(page + 1, 1)
            context['prevPage'] = page - 1

            numPages = (totalresultsNumFound // size) + 1

            if context['page'] <= 4:
                context['prevPageLimit'] = 1
            else:
                context['prevPageLimit'] = context['page'] - 4

            diff = numPages - context['page']

            if numPages - context['page'] < 4:
                context['nextPageLimit'] = context['page'] + diff
            elif context['prevPageLimit'] < 2:
                context['nextPageLimit'] = min(9, numPages)
            else:
                context['nextPageLimit'] = context['page'] + 4

            context['prevPageList'] = [i for i in range(context['prevPageLimit'], context['page'])]
            context['nextPageList'] = [i for i in range(context['page'] + 1, context['nextPageLimit'] + 1)]

            return render(request, 'seer/results.html', context)
        else:
            return (
                request, 'seer/results.html',
                {'q': 'query', 'errormessage': 'Your search returned zero results, please try another query.'})


def Query(request):
    if request.method == 'GET':
        q = request.GET.get('query')
        start = int(request.GET.get('page', 1))

        if q is not None and len(q) > 1:
            return __search(request, q, start)
        else:
            return render(request, 'seer/index.html', {})


def Document(request, document_id):
    body = {
        "query": {
            "match": {
                "_id": document_id
            }
        }
    }
    res = es.search(index=ELASTIC_INDEX, body=body)
    results = res['hits']['hits']

    if len(results) == 0:
        raise Http404("Document does not exist")

    result = results[0]

    context = dict()
    context['docId'] = document_id
    context['title'] = result['_source']['metadata']['title']
    context['authors'] = __get_author_list(result)

    context['abstract'] = result['_source']['abstract']
    context['body'] = result['_source']['body_text']
    context['doi'] = result['_source']['doi']
    context['json'] = json.dumps(result, separators=(',', ':'))

    context['source'] = result['_source']['source_x']
    context['journal'] = result['_source']['journal']

    return render(request, 'seer/document.html', context)


def DocumentJson(request, document_id):
    body = {
        "query": {
            "match": {
                "_id": document_id
            }
        }
    }
    res = es.search(index=ELASTIC_INDEX, body=body)
    results = res['hits']['hits']

    if len(results) == 0:
        raise Http404("Document does not exist")

    return HttpResponse(json.dumps(results[0], sort_keys=True, indent=4), content_type="application/json")
