resource staticSite 'Microsoft.Web/staticSites@2022-09-01' = {
  name: 'chatbot-test'
  location: resourceGroup().location
  properties: {
    allowConfigFileUpdates: true
  }
  sku: {
    tier: 'Standard'
    name: 'Standard'
  }

  resource appsettings 'config' = {
    name: 'appsettings'
    properties: {
      PYTHON_ENABLE_INIT_INDEXING: '1'
    }
  }
}
