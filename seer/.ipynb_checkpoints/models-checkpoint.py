from django.db import models


# Create your models here.

class SearchResult:
    def __init__(self, resultid, content="No content found", fileurl="No URL found", title="No title found",
                 authors="No authors available", description="No description found", affiliation="No location found",
                 journal="No journal available", source="", doi=""):
        self.resultid = resultid
        self.content = content
        self.fileurl = fileurl
        self.title = title
        self.authors = authors
        self.description = description
        self.affiliation = affiliation
        self.journal = journal
        self.source = source
        self.doi = doi
