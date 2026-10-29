<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/3.0"
    xmlns:bldg="http://www.opengis.net/citygml/building/3.0"
    xmlns:gml="http://www.opengis.net/gml/3.2"
    xmlns:tade="https://example.org/cg3e/test-ade/1.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="https://example.org/cg3e/test-ade/1.0 https://example.org/cg3e/test-ade/1.0/test-ade.xsd">
  <core:cityObjectMember>
    <bldg:Building gml:id="B1">
      <bldg:class codeSpace="https://example.org/cg3e/test-ade/1.0/codelists/Building.BuildingClassValue.xml">T1</bldg:class>
      <bldg:adeOfAbstractBuilding>
        <tade:BuildingProperties>
          <tade:energyClass codeSpace="https://example.org/cg3e/test-ade/1.0/codelists/TestADE.EnergyClassValue.xml">A</tade:energyClass>
          <tade:certification>
            <tade:Certification>
              <tade:label>Class A certificate</tade:label>
            </tade:Certification>
          </tade:certification>
          <tade:refurbishment>Insulation</tade:refurbishment>
        </tade:BuildingProperties>
      </bldg:adeOfAbstractBuilding>
    </bldg:Building>
  </core:cityObjectMember>
  <core:cityObjectMember>
    <tade:Kiosk gml:id="K1">
      <tade:operatorName>Comune di Prova</tade:operatorName>
      <tade:electricityMeter>
        <tade:ElectricityMeter>
          <tade:meterKind codeSpace="https://example.org/cg3e/test-ade/1.0/codelists/TestADE.MeterKindValue.xml">smart</tade:meterKind>
        </tade:ElectricityMeter>
      </tade:electricityMeter>
    </tade:Kiosk>
  </core:cityObjectMember>
</core:CityModel>
