import inspect

from types import ModuleType

from .module_types import StubClass, StubFunction, StubParameter, StubProperty


class FObjectType:
    Function = 'function'
    Class = 'class'
    Property = 'property'
    Enum = 'type'


# -------------------------------------------------------------
#                       Helper Functios
# -------------------------------------------------------------

def GetObjectName(Object) -> str:
    return Object.__name__


def GetObjectType(Object) -> FObjectType:
    """ Get object type as a string """
    return GetObjectName(type(Object))


def IsPrivate(Object):
    """ Check if the name of an object begins with a underscore """
    return GetObjectName(Object).startswith("_")


def IsMethodStatic(Class, MethodName: str):
    """ 
    Check if a method is static
    Args:
        - Class: reference to the class
        - Method: Name of the method
    """
    return isinstance(inspect.getattr_static(Class, MethodName), staticmethod)


def GetModuleContent(Module: ModuleType):
    """ 
    Get all members in the pyfbsdk module
    returns: a tuple with (Functions, Classes, Enums)
    """
    Functions = [x[1] for x in inspect.getmembers(Module) if GetObjectType(x[1]) == FObjectType.Function and not IsPrivate(x[1])]
    Classes = [x[1] for x in inspect.getmembers(Module) if GetObjectType(x[1]) == FObjectType.Class]
    Enums = [x[1] for x in inspect.getmembers(Module) if GetObjectType(x[1]) == FObjectType.Enum]

    return (Functions, Classes, Enums)


def GetClassParents(Class):
    return Class.__bases__


def GetUniqueClassMembers(Class, Ignore = (), AllowedOverrides = ()):
    """ 
    Args:
        - Class {object}: reference to the class
        - Ignore {List[str]}: 
        - AlwaysAllow {List[str]}: Always allowed members named x, even if they exists in the parent class

    Returns: tuple("Name", Reference)
    """
    Members = inspect.getmembers(Class)
    ParentClass = GetClassParents(Class)[0]
    UniqueMemebers = [x for x in Members if (not hasattr(ParentClass, x[0]) and x[0] not in Ignore) or x[0] in AllowedOverrides]  # and not x[0].startswith("__")

    return UniqueMemebers


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


def GetFunctionInfoFromDocString(Function) -> list[tuple[list[StubParameter], str]]:
    """
    Get Parameters & Return type from the docstring, can return multiple results if overload functions exists.

    Returns: a list of tuple([Parameters], ReturnType)
    """
    def _GenerateParams(ParamsString, DefaultValue = None) -> list[StubParameter]:
        """ 
        Parse a param string that looks something like this:
        "(FBVector4d)arg1, (FBVector4d)arg2, (FBVector4d)arg3"
        and generate StubParameter instances from it
        """
        Params = []
        for Param in ParamsString.split(","):
            # Param will now look something like this: '(str)arg1'
            ParamType, _, ParamName = Param.strip().partition(")")
            ParameterInstance = StubParameter(Function, ParamName, ParamType[1:], DefaultValue = DefaultValue)
            Params.append(ParameterInstance)
        return Params

    if not Function.__doc__:  # No docstring
        return []

    FunctionParamters = []
    # Read the docstring and split it up if there are multiple function overrides
    FunctionsDocs = [x for x in Function.__doc__.split("\n") if x]
    for Doc in FunctionsDocs:
        # 'Doc' will now look something like this:
        # ShowToolByName( (str)arg1 [, (object)arg2]) -> object
        Doc = Doc.partition("(")[2]  # Remove function name
        Params, _, ReturnType = Doc.rpartition("->")

        # Split params into required & optional
        Params = Params.rpartition(")")[0]
        RequiredParams, _, OptionalParams = Params.partition("[")
        OptionalParams = OptionalParams.replace("[", "").replace("]", "").lstrip(',')

        Params = []
        if RequiredParams.strip():
            Params += _GenerateParams(RequiredParams)
        if OptionalParams.strip():
            Params += _GenerateParams(OptionalParams, DefaultValue = "None")

        FunctionParamters.append(
            (Params, ReturnType.strip())
        )

    return FunctionParamters


def GetDataTypeFromPropertyClassName(ClassName: str, AllClassNames: list[str]):
    """
    Get the `Data` property type for a class that inherits from `FBProperty`
    This is done by removing e.g. `FBProperty` from the class name. Example: `FBPropertyVector3d` -> `Vector3d`
    """

    # Value to return use if a valid class could not be found for the given ClassName
    DefaultValue = "Any"

    ConvertTypeDict = {
        "Bool": "bool",
        "String": "str",
        "Int": "int",
        "Int64": "int",
        "UInt64": "int",
        "Float": "float",
        "Double": "float"
    }

    DataType = ClassName
    for x in ("FBProperty", "Animatable", "List"):
        DataType = DataType.replace(x, "")

    if DataType in ConvertTypeDict:
        return ConvertTypeDict[DataType]

    # For the base classes e.g. FBProperty
    if not DataType:
        return DefaultValue

    # TODO: Validate that the class actually exists
    DataType = f"FB{DataType}"
    if DataType not in AllClassNames:
        return DefaultValue

    return DataType


# -------------------------------------------------------------
#                     Generator Functions
# -------------------------------------------------------------


def GenerateEnumInstance(Class, ParentClass = None):
    """
    Generate a StubClass instance from a class (enum) reference

    Args:
        - Class: reference to the class
        - ParentClass: If this class is a subclass, the parent class should be passed along
    """
    # Create the stub instance
    ClassName = GetObjectName(Class)
    EnumClassInstance = StubClass(Class, ClassName)

    # Get all members and generate stub properties of them
    ClassMemebers = GetUniqueClassMembers(Class, Ignore = ["__init__", "__slots__", "names", "values"])
    for PropertyName, PropertyReference in ClassMemebers:
        PropertyInstance = StubProperty(PropertyReference, PropertyName)
        if ParentClass:
            PropertyInstance.Type = f"{GetObjectName(ParentClass)}.{ClassName}"
        else:
            PropertyInstance.Type = ClassName
        EnumClassInstance.AddProperty(PropertyInstance)

    EnumClassInstance.AddParent("_Enum")

    return EnumClassInstance


def GenerateClassInstance(Class, AllClassNames: list[str]) -> StubClass:
    """
    Generate a StubClass instance from a class reference

    Args:
        - Class {class}: reference to the class
    """
    # Create the stub instance
    ClassName = GetObjectName(Class)
    ClassInstance = StubClass(Class, ClassName)

    # Get all members and generate stub properties of them
    ClassMemebers = GetUniqueClassMembers(Class, Ignore = ["__instance_size__"], AllowedOverrides = ["__init__", "__getitem__", "Data"])
    ClassMemberNames = [x for x, y in ClassMemebers]

    for MemberName, MemberReference in ClassMemebers:
        Type = GetObjectType(MemberReference)

        if Type == FObjectType.Function:
            Methods = []
            for StubMethod in GenerateFunctionInstances(MemberReference):
                StubMethod.bIsStatic = IsMethodStatic(Class, MemberName)
                Methods.append(StubMethod)
            ClassInstance.AddFunctions(Methods)

        elif Type == FObjectType.Enum:
            StubEnum = GenerateEnumInstance(MemberReference, ParentClass = Class)
            ClassInstance.AddEnum(StubEnum)

        elif MemberName not in ["__init__"]:
            Property = StubProperty(MemberReference, MemberName)
            if Type in ClassMemberNames:
                Property.Type = f"{ClassName}.{Type}"
            elif MemberName == "Data" and "FBProperty" in ClassName and Type == FObjectType.Property:
                Property.Type = GetDataTypeFromPropertyClassName(ClassName, AllClassNames)
            else:
                Property.Type = Type

            ClassInstance.AddProperty(Property)

    # Set the parent classes
    for ParentClassName in GetClassParentNames(Class):
        ClassInstance.AddParent(ParentClassName)

    return ClassInstance


def GenerateFunctionInstances(Function) -> list[StubFunction]:
    """
    Generate StubFunction instances from a function reference.

    Args:
        - Function {function}: reference to the function

    Returns: A list of function instances, can be multiple if it has overload versions
    """
    FunctionName = GetObjectName(Function)

    StubFunctions = []

    # Get param & returntype info from the docstring
    FunctionInfo = GetFunctionInfoFromDocString(Function)
    for Parameters, ReturnType in FunctionInfo:
        StubFunctionInstance = StubFunction(Function, FunctionName, Parameters, ReturnType)

        # If multiple versions of this function exists, set the functions to be overloads
        StubFunctionInstance.bIsOverload = len(FunctionInfo) > 1

        StubFunctions.append(StubFunctionInstance)

    return StubFunctions


# -------------------------------------------------------------
#                     Main Generator Class
# -------------------------------------------------------------

def GenerateModuleSubs(Module: ModuleType):
    Functions, Classes, Enums = GetModuleContent(Module)

    AllClassNames = [x.__name__ for x in Classes + Enums]

    EnumStubs = [GenerateEnumInstance(Enum) for Enum in Enums]
    ClassStubs = [GenerateClassInstance(Class, AllClassNames) for Class in Classes]

    FunctionStubs: list[list[StubFunction]] = []
    for Function in Functions:
        FunctionStubs.append(GenerateFunctionInstances(Function))

    return EnumStubs, ClassStubs, FunctionStubs