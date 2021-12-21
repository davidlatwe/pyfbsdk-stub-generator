import tempfile
import shutil
import json
import os
import re

from urllib import request
from html.parser import HTMLParser

# https://download.autodesk.com/us/motionbuilder/sdk-documentation/
# https://download.autodesk.com/us/motionbuilder/sdk-documentation/contents-data.html

# https://help.autodesk.com/view/MOBPRO/2020/ENU/
# https://help.autodesk.com/view/MOBPRO/2020/ENU/?guid=__py_ref_index_html
# https://help.autodesk.com/view/MOBPRO/2022/ENU/?guid=MotionBuilder_SDK_py_ref_index_html

MOBU_DOCS_VIEW_URL = "https://help.autodesk.com/view/MOBPRO/"
MOBU_DOCS_COULDHELP_URL = "https://help.autodesk.com/cloudhelp/"

DOC_GUIDE_CONTENTS_PATH = "ENU/data/toctree.json"

PYFBSDK_PATH = "ENU/MotionBuilder-SDK/py_ref/group__pyfbsdk.js"
PYFBSDK_ADDITIONS_PATH = "ENU/MotionBuilder-SDK/py_ref/group__pyfbsdk__additions.js"
PYTHON_EXAMPLES_PATH = "ENU/MotionBuilder-SDK/py_ref/examples.js"

SDK_CPP_PATH = "ENU/MotionBuilder-SDK/cpp_ref/"
SDK_CLASSES_PATH = SDK_CPP_PATH + "annotated_dup.js"
SDK_FILES_PATH = SDK_CPP_PATH + "files_dup.js"
# DOCS_URL = "https://download.autodesk.com/us/motionbuilder/sdk-documentation/"
# TABLE_OF_CONTENT_URL = "%sscripts/toc-treedata.js" % DOCS_URL

DOCUMENTATION_DIR = os.path.join(
    os.path.dirname(__file__), "..", "documentation")


class FDictTags:
    Title = "ttl"
    Url = "ln"
    Id = "id"
    Children = "children"
    Ic = "ic"

    def Values(self):
        Values = [getattr(self, x) for x in dir(self) if not x.startswith("_")]
        return [x for x in Values if isinstance(x, str)]


class EPageType:
    Unspecified = -1
    Guide = 0
    C = 1
    Python = 2
    Examples = 3


# ------------------------------------------
#           Helper Functions
# ------------------------------------------

def GetFullURL(Version, Path, bIsSDK = False):
    BaseURL = MOBU_DOCS_COULDHELP_URL if bIsSDK else MOBU_DOCS_VIEW_URL
    return "%s%s/%s" % (BaseURL, Version, Path)


def GetUrlContent(Url: str):
    print("WEB CALL TO %s" % Url)
    Response = request.urlopen(Url)
    return Response.read().decode('utf-8')


def GetCacheFolder():
    return os.path.join(tempfile.gettempdir(), "mobu-docs-cache")


def GetCacheFilepath(RelativeUrl):
    return os.path.join(GetCacheFolder(), *RelativeUrl.split("/"))


def ClearCache():
    shutil.rmtree(GetCacheFolder())


def ReadFile(Filepath):
    with open(Filepath, "r") as File:
        return File.read()


def SaveFile(Filepath, Content):
    # Make sure folder exists before writing the file
    if not os.path.isdir(os.path.dirname(Filepath)):
        os.makedirs(os.path.dirname(Filepath))

    with open(Filepath, "w+") as File:
        File.write(Content)

# ------------------------------------------
#               DocPage Parser
# ------------------------------------------


class FMoBuDocsParserItem():
    Item = "memitem"
    Name = "memname"
    Doc = "memdoc"
    ParameterNames = "paramname"
    ParameterTypes = "paramtype"
    
    def GetValues():
        Values = [getattr(FMoBuDocsParserItem, x) for x in dir(FMoBuDocsParserItem) if not x.startswith("_")]
        return [x for x in Values if isinstance(x, str)]


class FMoBoDocsParameterNames():
    NoDefaultValue = "NoDefaultValue"


class MoBuDocsHTMLParser(HTMLParser):
    def __init__(self, *, convert_charrefs: bool = ...):
        super().__init__(convert_charrefs=convert_charrefs)

        self.Items = []
        self.CurrentItem = None
        self.CurrentDataTag = None
        self.bCollectingDocData = False

    def handle_starttag(self, tag, attrs):
        Attributes = dict(attrs)
        if tag == "div":
            ClassName = Attributes.get("class")
            if ClassName == FMoBuDocsParserItem.Item:
                if self.CurrentItem:
                    self.Items.append(self.CurrentItem)
                self.CurrentItem = {}
            if ClassName == FMoBuDocsParserItem.Doc:
                self.CurrentDataTag = FMoBuDocsParserItem.Doc
        elif tag == "td" and not self.CurrentDataTag:
            ClassName = Attributes.get("class")
            if ClassName in FMoBuDocsParserItem.GetValues():
                self.CurrentDataTag = ClassName

    def handle_endtag(self, tag):
        if self.CurrentDataTag == FMoBuDocsParserItem.Doc:
            if tag == "div":
                self.CurrentDataTag = None
        elif tag == "td":
            self.CurrentDataTag = None
        elif tag == "body" and self.CurrentItem:
            self.Items.append(self.CurrentItem)

    def handle_data(self, Data):
        #Data = Data.strip()
        if self.CurrentDataTag and self.CurrentItem != None and Data.strip():
            CurrentText = self.CurrentItem.get(self.CurrentDataTag, "")
            if CurrentText:
                CurrentText += " "
            if self.CurrentDataTag != FMoBuDocsParserItem.Doc:
                Data = Data.strip()
            self.CurrentItem[self.CurrentDataTag] = CurrentText + Data

    def GetMembers(self):
        return [MoBuDocMember(x) for x in self.Items]
        


class MoBuDocParameter():
    def __init__(self, Name, Type, Default = FMoBoDocsParameterNames.NoDefaultValue):
        self.Name = Name
        self.Type = Type
        self.Default = Default

    def __repr__(self):
        return '<object %s, %s:%s = %s>' % (type(self).__name__, self.Name, self.Type, self.Default)


class MoBuDocMember():
    def __init__(self, Data):
        self.Name = ""
        self.Type = None
        self.Params = []
        self.DocString = ""

        self.LoadData(Data)

    def LoadData(self, Data):
        # Name & Type
        self.Name = CPlusVariableNamesToPython(Data.get(FMoBuDocsParserItem.Name, ""))
        if " " in self.Name:
            try:
                self.Type, self.Name = self.Name.split(" ")
            except Exception as e:
                print("Name that could not be split: %s" % self.Name)
                return

        # Parameters
        ParameterTypes = Data.get(FMoBuDocsParserItem.ParameterTypes)
        ParameterNames = Data.get(FMoBuDocsParserItem.ParameterNames)
        if ParameterTypes and ParameterNames:
            ParameterTypes = CPlusVariableNamesToPython(ParameterTypes).split(" ")
            ParameterNames = ParameterNames.split(",")
            if len(ParameterNames) != len(ParameterTypes):
                raise Exception("Lenght of ParamTypes & ParamNames does not match! (in: %s)\n%s\n%s" % (self.Name, str(ParameterNames), str(ParameterTypes)))
            for Type, Name in zip(ParameterTypes, ParameterNames):
                DefaultValue = FMoBoDocsParameterNames.NoDefaultValue
                if "=" in Name:
                    Name, DefaultValue = (x.strip() for x in Name.split("="))
                self.Params.append(MoBuDocParameter(Name, Type, DefaultValue))

        # Doc String
        self.DocString = Data.get(FMoBuDocsParserItem.Doc)


def CPlusVariableNamesToPython(Text):
    for Char in ["(void *)", "*", "&", "const", "K_DEPRECATED", "virtual", "static", "unsigned"]:
        Text = Text.replace(Char, "")
        
    if "<" in Text and ">" in Text:
        # Handle Arrays
        Text = re.sub(r"[A-z]*\s*<\s*[A-z]*\s*>", "object", Text)
    return re.sub(' +', ' ', Text).strip()

# ------------------------------------------
#             Documentation Page
# ------------------------------------------

class MoBuDocumentationPageOLD():
    def __init__(self, PageInfo, bLoadPage = False):
        self._PageInfo = PageInfo
        self.Title = PageInfo.get(FDictTags.Title)
        self.Id = PageInfo.get(FDictTags.Id)
        self.RelativeURL = PageInfo.get(FDictTags.Url)
        self.Members = {}
        if bLoadPage:
            self.LoadPage()

    def __repr__(self):
        return '<object %s, "%s">' % (type(self).__name__, self.Title)

    def GetURL(self, bIncludeSideBar = False):
        if bIncludeSideBar:
            return DOCS_URL + "?url=%s,topicNumber=%s" % (self.RelativeURL, self.Id)
        return DOCS_URL + self.RelativeURL

    def LoadPage(self, bCache = False):
        CacheFilepath = GetCacheFilepath(self.RelativeURL)
        RawHTML = ""
        if bCache and os.path.isfile(CacheFilepath):
            RawHTML = ReadFile(CacheFilepath)
        else:
            RawHTML = GetUrlContent(self.GetURL())
            if bCache:
                SaveFile(CacheFilepath, RawHTML)
        Parser = MoBuDocsHTMLParser()
        Parser.feed(RawHTML)
        
        self.Members = {x.Name:x for x in Parser.GetMembers()}

    def GetMember(self, Name):
        return self.Members.get(Name, None)


class MoBuDocumentationCategory(MoBuDocumentationPageOLD):
    def __init__(self, PageInfo):
        super().__init__(PageInfo)
        self.Pages = []
        self.SubCategories = []
        self.LoadChildren(PageInfo)

    def LoadChildren(self, PageInfo):
        for ChildPage in PageInfo.get(FDictTags.Children, []):
            if FDictTags.Children in ChildPage:
                self.SubCategories.append(MoBuDocumentationCategory(ChildPage))
            else:
                self.Pages.append(MoBuDocumentationPageOLD(ChildPage))

    def FindPage(self, PageName, bLoadPage = False, bCache = False):
        for Page in self.Pages:
            if Page.Title == PageName:
                return Page
        for SubCategory in self.SubCategories:
            Page = SubCategory.FindPage(PageName, bLoadPage)
            if Page:
                if bLoadPage:
                    Page.LoadPage(bCache)
                return Page


class MoBuDocumentationPage():
    def __init__(self, Version, Title, RelativeURL, Id = None, bLoadPage = False):
        self.Version = Version
        self.Title = Title
        self.RelativeURL = RelativeURL
        self.Id = Id
        self.bIsLoaded = False
        self.Members = {}
        if bLoadPage:
            self.LoadPage()

    def __repr__(self):
        return '<object %s, "%s">' % (type(self).__name__, self.Title)

    def GetURL(self):
        return GetFullURL(self.Version, self.RelativeURL, bIsSDK = True)

    def LoadPage(self, bCache = False):
        if self.bIsLoaded:
            return
        CacheFilepath = GetCacheFilepath(self.RelativeURL)
        RawHTML = ""
        if bCache and os.path.isfile(CacheFilepath):
            RawHTML = ReadFile(CacheFilepath)
        else:
            RawHTML = GetUrlContent(self.GetURL())
            if bCache:
                SaveFile(CacheFilepath, RawHTML)
        Parser = MoBuDocsHTMLParser()
        Parser.feed(RawHTML)
        
        self.Members = {x.Name:x for x in Parser.GetMembers()}

    def GetMember(self, Name):
        return self.Members.get(Name, None)


# ------------------------------------------
#             Table of Contents
# ------------------------------------------

class MotionBuilderDocumentation():
    def __init__(self, Version, bCache = False):
        self.Version = Version
        self.bCache = bCache
        self._TableOfContents = []
        self._SDKClasses = {}

    def GetSDKClasses(self):
        if self._SDKClasses:
            return self._SDKClasses
        ClassesContent = GetDocsContent(self.Version, SDK_CLASSES_PATH)
        self._SDKClasses = {x[0]: MoBuDocumentationPage(self.Version, x[0], SDK_CPP_PATH + x[1]) for x in ClassesContent}
        return self._SDKClasses
    
    def GetSDKClassByName(self, ClassName, bLoadPage = True):
        Page = self.GetSDKClasses().get(ClassName)
        if Page and bLoadPage:
            Page.LoadPage(self.bCache)
        return Page

    def LoadTableOfContents(self):
        self._TableOfContents = [MoBuDocumentationCategory(x) for x in GetDocsTableOfContent(self.Version)]
        return self._TableOfContents

    def FindPage(self, PageName, PageType = EPageType.Unspecified, bLoadPage = True) -> MoBuDocumentationPageOLD:
        if PageType != EPageType.Unspecified:
            return self._TableOfContents[PageType].FindPage(PageName, bLoadPage, self.bCache)

        for ContentDict in self._TableOfContents:
            Page = ContentDict.FindPage(PageName, bLoadPage, self.bCache)
            if Page:
                return Page


def GetDocsContent(Version, Path):
    Content = GetUrlContent(GetFullURL(Version, Path, bIsSDK = True))

    # Make content python readable
    Content = Content.replace(", null ]", ",None]")  # Replace null with None
    Content = Content.split("=", 1)[1].strip()  # Remove e.g. 'var annotated_dup = '

    if Content.endswith(";"):
        Content = Content[:-1]

    return eval(Content)


def GetDocsTableOfContent(Version) -> list:
    """
    Parse the raw table of content .json file downloaded from the autodesk documentation webpage
    """
    RawContent = GetUrlContent(GetFullURL(Version, DOC_GUIDE_CONTENTS_PATH))
    TableOfContent = json.loads(RawContent)
    return TableOfContent["books"]