from django.http import Http404, HttpResponse
from django.shortcuts import render
from django import template
from . import models
from elasticsearch import Elasticsearch

import json

ERR_QUERY_NOT_FOUND = '<h1>Query not found</h1>'
ERR_IMG_NOT_AVAILABLE = 'The requested result can not be shown now'

# USER = open("elastic-settings.txt").read().split("\n")[1]
# PASSWORD = open("elastic-settings.txt").read().split("\n")[2]
ELASTIC_INDEX = 'cord_temp'

# open connection to Elastic
es = Elasticsearch(['http://csxindex05:9200/'], verify_certs=True)
register = template.Library()

if not es.ping():
    raise ValueError("Connection failed")

@register.filter
def subtract(value, arg):
    return value - arg

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
            #print(first_name)
        else:
            author['name'] = ' '.join([first_name, last_name, suffix])
            #print("SUFFIX:", suffix)

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

        #print(author)
        author_list.append(author)

    return author_list

def aggs():
    agg_query = {
                "uniq_sources" : {
                    "cardinality" : {
                        "field" : "source_x.keyword"
                    }
                },
                "uniq_journals": {
                    "cardinality" : {
                        "field" : "journal.keyword"
                    }
                },
                "sources":{
                    "terms":{
                        "field":"source_x.keyword"
                    }
                },
                "journals":{
                    "terms":{
                        "field":"journal.keyword"
                    }
                },
                "uniq_years":{
                    "cardinality" : {
                        "field" : "publish_year.keyword"
                    }
                },
                "year":{
                    "terms":{
                        "field":"publish_year.keyword"
                    }
                },
                "contains_abstract":{
                    "filters":{
                        "filters": {
                            "abs":{"match":{"abstract.keyword":""}},
                            "fulltext":{"match":{"body_text":""}}
                        }
                    }
                },
                "first":{
                    "cardinality": {
                        "field": "metadata.authors.fullname.keyword"
                    }
                },
                "middle":{
                     "cardinality": {
                        "field": "metadata.authors.middle.keyword"
                    }
                },
                "last":{
                     "cardinality": {
                        "field": "metadata.authors.last.keyword"
                    }
                },
                "full_name":{
                    "terms": {
                        "field": "metadata.authors.fullname.keyword",
                        "size":20,
                        "order" : { "_count" : "desc" }
                    }
                }
            }
    
    return agg_query

def add_source_filters(template,filter_query,source):
    source = source.split(',')
    source_filter = template

    if len(source)>0:
        for x in source:
            source_filter['bool']['should'].append({
                "match_phrase": {
                    "source_x.keyword": {
                      "query": x
                        }
                    }
                })
        filter_query.append(source_filter)
    return filter_query


def add_journal_filters(template,filter_query,journal):
    journal = journal.split(',')
    journal_filter = template
    if len(journal)>0:
        for x in journal:
            journal_filter['bool']['should'].append({
                "match_phrase": {
                    "journal.keyword": {
                      "query": x
                        }
                    }
                })
        filter_query.append(journal_filter)
    return filter_query


def add_year_filters(template,filter_query,year):
    year = year.split(',')
    year_filter = template
    if len(year)>0:
        for x in year:
            year_filter['bool']['should'].append({
                "match_phrase": {
                    "publish_year.keyword": {
                      "query": x
                        }
                    }
                })
        filter_query.append(year_filter)
    return filter_query

def add_authors_filters(template,filter_query,author):
    author = author.split(',')
    author_filter = template
    if len(author)>0:
        for x in author:
            author_filter['bool']['should'].append({
                "match_phrase": {
                    "metadata.authors.fullname.keyword": {
                      "query": x
                        }
                    }
                })
        filter_query.append(author_filter)
    return filter_query

def remove_punct(my_str):
    punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~'''
    # To take input from the user
    # my_str = input("Enter a string: ")

    # remove punctuation from the string
    no_punct = ""
    for char in my_str:
        if char not in punctuations:
            no_punct = no_punct + char

    # display the unpunctuated string
    return no_punct

def remove_stop(query):
    with open('/data/CoronaSeer/seer/englishST.txt') as f:
        all_stopwords = f.readlines()
    # you may also want to remove whitespace characters like `\n` at the end of each line
    all_stopwords = [x.strip() for x in all_stopwords] 
    text_tokens = query.split(' ')
    query = [word for word in text_tokens if not word in all_stopwords]
    query = ' '.join(query)
    return query

def __search(request, query, page, source="",journal="",full_text="",abstract="",author="",year=""):
    
    query = query.lower()
    query = remove_punct(query)
    query = remove_stop(query)
    
    print(query)
    print("SOURCE:", source)
    print("JOURNAL:", journal)
    print("FULL TEXT:", full_text)
    print("ABSTRACT:", abstract)
    print("AUTHOR:", author)

    template = {
        "bool":{
            "should":[]
        }
    }
    filter_query =[]
    if source:
        filter_query = add_source_filters(template,filter_query,source)
    if journal:
        filter_query = add_journal_filters(template,filter_query,journal)
    if year:
        filter_query = add_year_filters(template,filter_query,year)
    if author:
        filter_query = add_authors_filters(template,filter_query,author)
    size = 15
    start = (page - 1) * size
    body = {
        "from": start,
        "size": size,
        "query": {
            "bool": {
                "filter": [
                    {
                    "multi_match": {
                            "query": query,
                            "fields":  ["body_text","abstract^2", "metadata.title^3"],
                            "type": "cross_fields"
                        }
                     }
                ],
                "must":[]
            }
        },
        "aggs" : aggs(),
        'highlight': {'fields': {'body_text': {}, 'abstract.text': {}}}
    }
    if len(filter_query)>0:
        for each_filter in filter_query:
            body['query']['bool']['must'].append(each_filter)
        #body['query']['bool']['minimum_should_match'] = 1
        body = body

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
        aggregations = res['aggregations']
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

                if not f.journal:
                    f.journal = 'N/A'

                SearchResults.append(f)
                
            context = dict()
            context['results'] = SearchResults
            context['q'] = query
            # Adding aggregations
            context['uniq_journals'] = aggregations['uniq_journals']['value']
            context['uniq_sources'] = aggregations['uniq_sources']['value']
            context['no_abstract'] =aggregations['contains_abstract']['buckets']['abs']['doc_count']
            context['no_fulltext'] =aggregations['contains_abstract']['buckets']['fulltext']['doc_count']
            context['uniq_authors'] = aggregations['first']['value']
            context['uniq_years']  =aggregations['uniq_years']['value']

            context['abstract_available'] = totalresultsNumFound - context['no_abstract'] 
            context['fulltext_available'] = totalresultsNumFound - context['no_fulltext']
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

            #Adding list of sources
            total_sources = len(res['aggregations']['sources']['buckets'])
            sources =[]
            if (total_sources > 0):
                for src in res['aggregations']['sources']['buckets']:
                    if src['key'] =='':
                        src['key']= "Unknown"
                    sources.append({'name':src['key'],'count':src['doc_count']})
            
            #Adding list of journals
            total_journals = len(res['aggregations']['journals']['buckets'])
            jnls =[]
            if (total_journals > 0):
                for jnl in res['aggregations']['journals']['buckets']:
                    if jnl['key'] =='':
                        jnl['key']= "Unknown"
                    jnls.append({'name':jnl['key'],'count':jnl['doc_count']})
                                
            #Adding list of years
            total_years = len(res['aggregations']['year']['buckets'])
            yrs =[]
            if (total_years > 0):
                for yr in res['aggregations']['year']['buckets']:
                    if yr['key'] =='':
                        yr['key']= "Unknown"
                    yrs.append({'name':yr['key'],'count':yr['doc_count']})

            context['sources'] = sources
            context['journals'] = jnls
            context['years'] =  yrs

            #Adding authors to the list
            auths =[]
            fullname = res['aggregations']['full_name']['buckets']
            for name in fullname:
                auths.append({'name':name['key'],'count':name['doc_count']})

            context['authors'] = auths
            #print(context)
            return render(request, 'seer/results.html', context)

            

        else:
            return (
                request, 'seer/results.html',
                {'q': 'query', 'errormessage': 'Your search returned zero results, please try another query.'})




def Query(request):
    if request.method == 'GET':
        q = request.GET.get('query')
        start = int(request.GET.get('page', 1))
        
        source = request.GET.get('source')
        journal = request.GET.get('journal')
        full_text = request.GET.get('full_text')
        abstract = request.GET.get('abstract')
        author = request.GET.get('author')

        if q is not None and len(q) > 1:
            return __search(request, q, start, source, journal, full_text, abstract, author)
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

    if not context['journal']:
        context['journal'] = 'N/A'

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
