import xmlschema

xml_request = "request.xml"
xml_response_cpp = "response_cpp.xml"
xml_response_svn = "response_svn.xml"

def validate_xml(xml, xsdfile):
    # print("read: " + xsdfile)
    schema = xmlschema.XMLSchema(xsdfile)
    try:
        print("validate " + xml + " against " + xsdfile)
        schema.validate(xml)
    except Exception as e:
        print("Schema is not valid: " + str(e))
        raise Exception("Schema is not valid: " + str(e))
    # print("XML schema validation succeeded\n")


#print("validate proforma_2.1.xsd")
#schema = xmlschema.XMLSchema("../proforma_2.1.xsd")
print("validate praktomat_2.3.xsd")
schema = xmlschema.XMLSchema("../praktomat_2.3.xsd")
print("validate proforma_full_v2.1.xsd")
schema = xmlschema.XMLSchema("../proforma_full_v2.1.xsd")

print("")
# xml_request
is_valid = validate_xml(xml=xml_request, xsdfile="../proforma_2.1.xsd")
is_valid = validate_xml(xml=xml_request, xsdfile="../proforma_full_v2.1.xsd")
# is_valid = validate_xml(xml=xml_request, xsdfile="praktomat_2.3.xsd")

# xml_response_cpp
is_valid = validate_xml(xml=xml_response_cpp, xsdfile="../proforma_2.1.xsd")
is_valid = validate_xml(xml=xml_response_cpp, xsdfile="../proforma_full_v2.1.xsd")

# xml_response_cpp
is_valid = validate_xml(xml=xml_response_svn, xsdfile="../proforma_2.1.xsd")
is_valid = validate_xml(xml=xml_response_svn, xsdfile="../proforma_full_v2.1.xsd")