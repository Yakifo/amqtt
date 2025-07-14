export interface User {
  id: number
  username: string
  publish_acl: string[]
  subscribe_acl: string[]
  receive_acl: string[]
}

const gotNames = ['Jon Snow', 'Daenerys Targaryen', 'Tyrion Lannister', 'Arya Stark', 'Cersei Lannister', 'Sansa Stark', 'Jaime Lannister', 'Bran Stark', 'Jorah Mormont', 'Theon Greyjoy', 'Samwell Tarly', 'Lord Varys', 'Brienne of Tarth', 'Davos Seaworth', 'Melisandre', 'Bronn', 'Missandei', 'Eddard Stark', 'Catelyn Stark', 'Petyr Baelish']

export const generateRandomID = () => Math.floor(Math.random() * 10000)

const generateUser = (name: string): User => ({
  id: generateRandomID(),
  username: name,
  publish_acl: ['publish/acl/topic',],
  subscribe_acl: [],
  receive_acl: []
})

export const users = (): User[] => {
  return gotNames.map(name => generateUser(name))
};
