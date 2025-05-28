targetScope = 'subscription'

resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'chatbot'
  location: 'westeurope'
}

module web './web.bicep' = {
  name: 'web'
  scope: rg
  params: {
  }
}
