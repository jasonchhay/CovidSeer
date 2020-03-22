from django.db import models


# Create your models here.

class SearchResult:
    def __init__(self, resultid, content="No content found", fileurl="No URL found", title="No title found",
                 description="No description found"):
        self.resultid = resultid
        self.content = content
        self.fileurl = fileurl
        self.title = title
        self.description = description
