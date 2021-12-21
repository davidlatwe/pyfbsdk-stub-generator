#
#   Code to generate a pyfbsdk stub file
#

# Make sure code is running inside of MotionBuilder
try:
    import pyfbsdk
except:
    raise Exception("Code running outside of MotionBuilder. Please run this inside of the MotionBuilder version you want to generate a stub file for.")


import importlib
import inspect
import typing
import pydoc
import time
import sys
import os
import re

from importlib import reload

# Append current directory to path to be able to import modules
sys.path.append(os.path.dirname(__file__))

import motionbuilder_documentation_parser as docParser
reload(docParser)


# Modules to generate a doc for
import pyfbsdk_additions
import pythonidelib
import pyfbsdk

MODULES = [
    (pyfbsdk, "pyfbsdk_gen_doc"),
    (pythonidelib, "")
    ]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "generated-stub-files")

TAB_CHAR = "    "

# ---------------------------
#     Enums And Structs
# ---------------------------

VariableTypeRenames = {
    "double": "float",
    "String": "str",
    "Int": "int",
    "Float": "float",
    "Bool": "bool",
    "char": "str",
    "FBVector4object": "FBVector4d",
    "FBTVector": "FBVector3d",
}

class FObjectType:
    Function = 'function'
    Class = 'class'
    Property = 'property'
    Enum = 'type'

# --------------------------------------------------------
#                    Patch Functions
# --------------------------------------------------------

def PatchGeneratedDocString(Text):
    # Replace content
    for TagName, ReplaceWith in [("<b>", ""), ("</b>", ""), ("b>", ""), ("\\", "\\\\")]:
        Text = Text.replace(TagName, ReplaceWith)
        
    # Patch @code, example:
    #   @code
    #   print("Hello World")
    #   @endcode
    if "@code" in Text:
        NewText = ""
        bInCodeBlock = False
        bFirstCodeLine = False
        for Line in Text.split("\n"):
            Line += "\n"
            if bInCodeBlock:
                if Line.startswith("@endcode"):
                    bInCodeBlock = False
                    Line = "\n"
                elif not Line.strip():
                    continue
                else:
                    if Line.strip().startswith("//"):
                        Line = Line.replace("//", "#")
                    if not bFirstCodeLine:
                        Line = "    %s" % Line
                bFirstCodeLine = False
            elif Line.startswith("@code"):
                bFirstCodeLine = True
                bInCodeBlock = True
                Line = "\n>>> "
            
            NewText += Line
        Text = NewText
        
    # Remove p prefix from parameters, example: pVector -> Vector
    Text = re.sub(r"\s(p)([A-Z])", r"\2", Text)
        
    return Text.strip()



def PatchArgumentName(Param:str):
    # Remove the 'p' prefix
    if Param.startswith("p"):
        if not (len(Param) == 2 and Param[1].isdigit()):   
            Param = Param[1:]
    
    if Param == "True":
        Param = "bState"
        
    return Param

def PatchVarialbeType(VariableType: str, AllClassNames, Default = None):
    NewVariableType = VariableType
    if VariableType.startswith("FBPropertyAnimatable"):
        NewVariableType = VariableType.replace("PropertyAnimatable", "", 1)
    elif VariableType.startswith("FBProperty"):
        NewVariableType = VariableType.replace("Property", "", 1)
    
    for Key, Value in VariableTypeRenames.items():
        if Key.lower() == NewVariableType.lower() or ("FB%s"% Key).lower() == NewVariableType.lower():
            return Value
        
    if NewVariableType in AllClassNames:
        return NewVariableType
    
    if VariableType in AllClassNames:
        return VariableType
    
    return Default

# --------------------------------------------------------
#                       Classes
# --------------------------------------------------------

class StubMainClass():
    def __init__(self, Name="", Indentation = 0) -> None:
        self.Name = Name
        self._DocString = ""
        self.SetIndentationLevel(Indentation)
        
    def SetIndentationLevel(self, Level:int):
        self._Indentation = Level
        
    def GetAsString(self):
        raise NotImplementedError("GetAsString() has not yet been implemented")
    
    def SetDocString(self, Text):
        self._DocString = PatchGeneratedDocString(Text)
    
    def GetDocString(self):
        if self._DocString:
            return '"""%s"""' % self._DocString
        return ""
    
    def Indent(self, Text, bCurrent = False):
        Level = self._Indentation if bCurrent else self._Indentation + 1
        return "\n".join([(TAB_CHAR * Level) + Line.strip() for Line in Text.split("\n")])
    
    def GetRequirements(self) -> list:
        raise NotImplementedError("GetRequirements() has not yet been implemented")


class StubFunction(StubMainClass):
    def __init__(self, Name="", Indentation = 0):
        super().__init__(Name=Name, Indentation = Indentation)
        self.Params = []
        self.ReturnType = None
        self.bIsClassFunction = False
    
    def GetParamsAsString(self):
        # self.Params = [("Name", "Type")]
        ParamString = ""
        for Index, Param in enumerate(self.Params):
            if self.bIsClassFunction and Index == 0:
                ParamString += "self"
            else:
                ParamString += Param[0]
                if Param[1]:
                    ParamString += ":%s" % Param[1]
            ParamString += ","
            
        return ParamString[:-1]
    
    def GetRequirements(self):
        Parameters = self.Params[1:] if self.bIsClassFunction else self.Params
        return [x[1] for x in Parameters if x[1] and x[1].startswith("FB")]
    
    def GetAsString(self):
        FunctionAsString = self.Indent(
            'def %s(%s)' %(self.Name, self.GetParamsAsString()), 
            bCurrent = True
            )
        
        if self.ReturnType and self.ReturnType != "None":
            FunctionAsString += '->%s' % self.ReturnType
            
        FunctionAsString += ":"
        
        DocString = self.GetDocString()
        if DocString:
            FunctionAsString += "\n%s\n%s" % (self.Indent(DocString), self.Indent("..."))
        else:
            FunctionAsString += "..."
        
        return FunctionAsString


class StubClass(StubMainClass):
    def __init__(self, Name="", Indentation = 0):
        super().__init__(Name = Name, Indentation = Indentation)
        self.Parents = []
        self.StubProperties = []
        self.StubFunctions = []
        
    def GetRequirements(self) -> list:
        return self.Parents
        Requirements = []
        # Get requirements for all functiosn & properties
        for Object in self.StubProperties + self.StubFunctions:
            Requirements.extend(Object.GetRequirements())
        
        # Add Parent class names as requirements
        return Requirements + self.Parents

    def GetAsString(self):
        ParentClassesAsString = ','.join(self.Parents)
        ClassAsString = "class %s(%s):\n" % (self.Name, ParentClassesAsString)
        
        if self.GetDocString():
            ClassAsString += "%s\n" % self.Indent(self.GetDocString())
        
        ClassMembers = self.StubProperties + self.StubFunctions
        for StubObject in ClassMembers:
            StubObject.SetIndentationLevel(1)
            ClassAsString += "%s\n" % StubObject.GetAsString()
        
        # If class doesn't have any members, add a ...
        if not len(ClassMembers):
            ClassAsString += self.Indent("...")
        
        return ClassAsString.strip()

class StubProperty(StubMainClass):
    def __init__(self, Name="", Indentation = 0):
        super().__init__(Name=Name, Indentation = Indentation)
        self._Type = None
        
    def GetType(self):
        if self._Type:
            return self._Type
        return "property"
    
    def SetType(self, Type):
        self._Type = Type
        
    def GetRequirements(self):
        if self._Type and self._Type.startswith("FB"):
            return [self._Type]
        return []
        
    def GetAsString(self):
        PropertyAsString = self.Indent("%s:%s" % (self.Name, self.GetType()), bCurrent = True)
        if self.GetDocString():
            PropertyAsString += "\n"
            PropertyAsString += self.Indent(self.GetDocString(), bCurrent = True)

        return PropertyAsString


# --------------------------------------------------------
#                Helper functions
# --------------------------------------------------------

def GetMotionBuilderVersion():
    return int(2000 + pyfbsdk.FBSystem().Version / 1000)

def GetArgumentsFromFunction(Function):
    DocString = Function.__doc__
    HelpFunction = DocString.split("->", 1)[0]
    HelpArgumentString = HelpFunction.split("(", 1)[1].strip()[:-1]
    HelpArgumentString = HelpArgumentString.replace("]", "").replace("[", "")
    HelpArguments = HelpArgumentString.split(",")
    ReturnValue = []
    for Argument in HelpArguments:
        if not Argument:
            continue
        Type, ArgName = Argument.strip().split(")")
        ReturnValue.append((ArgName.strip(), Type[1:].strip()))
    return ReturnValue


def GetClassParents(Class):
    return Class.__bases__



def GetClassParentNames(Class):
    ParentClassNames = []
    for Parent in GetClassParents(Class):
        ParentClassName = Parent.__name__
        if ParentClassName == "instance":
            ParentClassName = ""

        elif ParentClassName == "enum":
            ParentClassName = "_Enum"
            
        ParentClassNames.append(ParentClassName)
    
    return ParentClassNames


def GetClassMembers(Class):
    IgnoreMembers = ["names", "values", "__slots__", "__instance_size__"]
    Members = inspect.getmembers(Class)
    ParentClass = GetClassParents(Class)[0]
    UniqueMemebers = [x for x in Members if not hasattr(ParentClass, x[0]) and x[0] not in IgnoreMembers and not x[0].startswith("__")]
    return UniqueMemebers


def GetObjectType(Object):
    return type(Object).__name__


def IsPrivate(Object):
    return Object.__name__.startswith("_")


# --------------------------------------------------------
#                   Generate Functions
# --------------------------------------------------------

def GenerateStubFunction(Function, DocMembers, Indentation = 0, bIsClassFunction = False):
    FunctionName:str = Function.__name__
    
    StubFunctionInstance = StubFunction(FunctionName, Indentation = Indentation)
    StubFunctionInstance.bIsClassFunction = bIsClassFunction
    
    # Parameters
    Parameters = GetArgumentsFromFunction(Function)
    
    DocRef = DocMembers.get(FunctionName)
    if DocRef:
        StubFunctionInstance.SetDocString(DocRef.__doc__)
        DocArguments = inspect.getargspec(DocRef).args
        Parameters = [(PatchArgumentName(Name), Arg[1]) for Name, Arg in zip(DocArguments, Parameters)]
    StubFunctionInstance.Params = Parameters
    
    # Return Type
    ReturnType = Function.__doc__.split("->", 1)[1].strip()
    if "\n" in ReturnType:
        ReturnType = ReturnType.split("\n")[0].strip()
    if ReturnType.endswith(":"):
        ReturnType = ReturnType[:-1].strip()
    StubFunctionInstance.ReturnType = ReturnType
        
    return StubFunctionInstance

def GenerateStubClass(Class, DocMembers, AllClassNames, MoBuDocumentation:docParser.MotionBuilderDocumentation = None, bVerbose = False):
    ClassName:str = Class.__name__
    DocClasses = [x for x in DocMembers if type(x).__name__ in ["class", "type"]]
    DocMemberNames = [x.__name__ for x in DocClasses]
    
    StubClassInstance = StubClass(ClassName)
    StubClassInstance.Parents = GetClassParentNames(Class)
    
    
    Page = MoBuDocumentation.GetSDKClassByName(ClassName) if MoBuDocumentation else None
    if not Page and bVerbose:
        print("Could not find SDK docs for: %s" %(ClassName))
    
    # TODO: DocMembers/DocGenRef etc. could be a class
    DocGenRef = DocMembers.get(ClassName)
    DocGenMembers = {}
    if DocGenRef:
        StubClassInstance.SetDocString(DocGenRef.__doc__)
        DocGenMembers = dict(GetClassMembers(DocGenRef))
        
    for Name, Reference in GetClassMembers(Class):
        MemberType = GetObjectType(Reference)
        DocWebMember = Page.GetMember(Name) if Page else None
        if MemberType == FObjectType.Function:
            try:
                StubClassInstance.StubFunctions.append(
                    GenerateStubFunction(Reference, DocGenMembers, bIsClassFunction = True)
                )
            except:
                if bVerbose: print("Failed for %s" % Name)
        else:
            Property = StubProperty(Name)
            if MemberType == FObjectType.Property:
                Type = DocWebMember.Type if DocWebMember else None
                if not Type:
                    try:
                        Type = eval("type(%s().%s).__name__" % (ClassName, Name))
                        if Type == "NoneType":
                            Type = None                            
                    except:
                        pass
                if Type:
                    Property.SetType(PatchVarialbeType(Type, AllClassNames))
            else:
                Property.SetType(ClassName)
            StubClassInstance.StubProperties.append(Property)
            PropertyDocGenRef = DocGenMembers.get(Name)
            if PropertyDocGenRef:
                Property.SetDocString(PropertyDocGenRef.__doc__)
            
    return StubClassInstance
    

def SortClasses(Classes):
    """ 
    Sort classes based on their parent class
    """
    i = 0
    ClassNames = [x.Name for x in Classes]
    while (i < len(Classes)):
        Requirements = Classes[i].GetRequirements()
        if Requirements:
            RequiredIndices = [ClassNames.index(x) for x in Requirements if x in ClassNames]
            RequiredMaxIndex = max(RequiredIndices) if RequiredIndices else -1
            if RequiredMaxIndex > i:
                Classes.insert(RequiredMaxIndex + 1, Classes.pop(i))
                ClassNames.insert(RequiredMaxIndex + 1, ClassNames.pop(i))
                i -= 1
        
        i += 1
        
    return Classes



def GenerateStub(Module, Filepath: str, SourcePyFile = ""):
    """
    Generate a stubfile
    
    * Module: Reference to a module to generate a stubfile
    * Filepath: The output abs filepath
    * SourcePyFile: If there exists a source .py file with doc comments (like pyfbsdk_gen_doc.py)
    """
    StartTime = time.time()
    
    # Find all Functions, Classes etc. inside of the module
    Functions = [x[1] for x in inspect.getmembers(Module) if GetObjectType(x[1]) == FObjectType.Function and not IsPrivate(x[1])]
    Classes = [x[1] for x in inspect.getmembers(Module) if GetObjectType(x[1]) == FObjectType.Class]
    Enums = [x[1] for x in inspect.getmembers(Module) if GetObjectType(x[1]) == FObjectType.Enum]
    Misc = [x for x in inspect.getmembers(Module) if GetObjectType(x[1]) not in [FObjectType.Function, FObjectType.Class, FObjectType.Enum]]
    
    # Get all members from the pre-generated doc/stub file 
    MoBuDocumentation = docParser.MotionBuilderDocumentation(GetMotionBuilderVersion(), bCache = True)
    DocMembers = {}
    if SourcePyFile:
        ImportedModule = importlib.import_module(SourcePyFile)
        DocMembers = dict(inspect.getmembers(ImportedModule))
    
    AllClassNames = [x.__name__ for x in Classes + Enums]
    
    # Construct stub class instances based on all functions & classes found in the module
    StubFunctions = [GenerateStubFunction(x, DocMembers) for x in Functions]
    StubClasses = [GenerateStubClass(x, DocMembers, AllClassNames, MoBuDocumentation, bVerbose = True) for x in Classes]
    StubEnums = [GenerateStubClass(x, DocMembers, AllClassNames) for x in Enums]
    
    Classes = SortClasses(StubClasses)
    
    # Generate the stub file content as a string 
    StubFileContent = ""
    
    # Extra custom additions
    AdditionsFilepath = os.path.join(os.path.dirname(__file__), "additions_%s.py" % Module.__name__)
    if os.path.isfile(AdditionsFilepath):
        with open(AdditionsFilepath, 'r') as File:
            StubFileContent += "%s\n" % File.read()        
    
    # Add Enums, Classes & Functions to the string
    StubFileContent += "%s\n" % "\n".join([x.GetAsString() for x in StubEnums + StubClasses + StubFunctions])
    
    # Write content into the file
    with open(Filepath, "w+") as File:
        File.write(StubFileContent)

    ElapsedTime = time.time() - StartTime
    print("Generating stub for module %s took %ss" %(Module.__name__, ElapsedTime))


def GenerateMotionBuilderStubFiles(OutputDirectory = ""):
    if not OutputDirectory:
        OutputDirectory = os.path.join(OUTPUT_DIR, "motionbuilder-%s" % GetMotionBuilderVersion())
        if not os.path.isdir(OutputDirectory):
            os.makedirs(OutputDirectory)
    
    for Module in MODULES:
        OutputFilepath = os.path.join(OutputDirectory, "%s.py" % Module[0].__name__)
        GenerateStub(Module[0], OutputFilepath, Module[1])


# if "builtin" in __name__:
GenerateMotionBuilderStubFiles()
