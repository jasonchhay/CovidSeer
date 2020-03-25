from django.shortcuts import render
from . import models
from elasticsearch import Elasticsearch

ERR_QUERY_NOT_FOUND = '<h1>Query not found</h1>'
ERR_IMG_NOT_AVAILABLE = 'The requested result can not be shown now'

# USER = open("elastic-settings.txt").read().split("\n")[1]
# PASSWORD = open("elastic-settings.txt").read().split("\n")[2]
ELASTIC_INDEX = 'cord'

# open connection to Elastic
es = Elasticsearch(['http://csxindex05:9200/'], verify_certs=True)

if not es.ping():
    raise ValueError("Connection failed")


# Include the following if user authentication is on (i.e., XPack is installed and linked with Elastic)
# http_auth=(USER, PASSWORD),

# SOLR_BASE_URL = "http://localhost:{0}/solr/{1}/select?&q=".format(SOLR_PORT,COLLECTION_NAME)
def Home(request):
    return render(request, 'seer/index.html')


def Query(request):
    if request.method == 'POST':
        q = request.POST.get('q', None)
        start = request.POST.get('start', 0)
        if q is not None and len(q) > 2:
            return Search(request, q, start)
        else:
            if q is None:
                return render(request, 'seer/index.html', {'errormessage': None})
            else:
                errormessage = 'Please use larger queries'
                return render(request, 'seer/index.html', {'errormessage': errormessage})
    else:
        # it's a get request, can come from two sources. if start=0
        # or start not in GET dictionary, someone is requesting the page
        # for the first time

        start = int(request.GET.get('start', 0))
        query = request.GET.get('q', None)
        if start == 0 or query == None:
            return render(request, 'seer/index.html')
        else:
            return search(request, query, start)


def Search(request, query, start):
    size = 10
    body = {
        "from": start,
        "size": size,
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["body", "abstract.text"],
                "operator": "and"
            }

        },
        'highlight': {'fields': {'body': {}}}
    }
    res = es.search(index=ELASTIC_INDEX, body=body)

    if not res.get('hits'):
        return render(request, 'seer/error.html',
                      {'errormessage': 'Your query returned zero results, please try another query'})
    else:
        print("search done")
        totalresultsNumFound = res['hits']['total']
        # hlresults=r.json()['highlighting']
        results = res['hits']['hits']
        print(res['hits']['hits'])
        SearchResults = []
        if len(results) > 0:
            for result in results:
                resultid = result['_id']
                f = models.SearchResult(resultid)  # calling the object class that is defined inside models.py

                f.content = result['_source']['body']

                # rawpath= result['_source']['file']['url']

                # removing local folder path
                f.url = result['_source']['metadata']['title']

                f.title = result['_source']['metadata']['title']
                # f.description = str(result['_source']['meta']['raw']['description'])
                f.description = ''
                if 'highlight' in result:
                    for desc in result['highlight']['body']:
                        f.description = f.description + desc + '\n'

                # f.description = " ".join(f.description).encode("utf-8")
                '''
                if len(result.get('category',[])) > 0:
                   f.category=result['category'][0].encode("utf-8") 
                '''
                # trying to use the location field to get the file name to display the image
                # f.filename= str(imageid)+'.png'
                SearchResults.append(f)

            return render(request, 'seer/results.html', {'results': SearchResults, 'q': query, \
                                                         'total': totalresultsNumFound, 'i': str(start + 1) \
                , 'j': str(len(results) + start)})
        else:
            return (
                request, 'seer/error.html',
                {'errormessage': 'Your search returned zero results, please try another query'})
