import xmlschema

xml = "request.xml"

def validate_xml(xml, xsdfile):
    print("read: " + xsdfile)
    schema = xmlschema.XMLSchema(xsdfile)
    try:
        print("validate")
        schema.validate(xml)
    except Exception as e:
        print("Schema is not valid: " + str(e))
        raise Exception("Schema is not valid: " + str(e))
    print("XML schema validation succeeded\n")


print("validate: " + xml)
is_valid = validate_xml(xml=xml, xsdfile="proforma_2.1.xsd")

print("read: praktomat_2.3.xsd")
schema = xmlschema.XMLSchema("praktomat_2.3.xsd")

is_valid = validate_xml(xml=xml, xsdfile="proforma_full_v2.1.xsd")