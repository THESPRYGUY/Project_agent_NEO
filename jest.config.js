module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests/js'],
  moduleNameMapper: {
    '^src/persona/(.*)$': '<rootDir>/src/persona/$1',
  },
  collectCoverageFrom: ['src/persona/**/*.ts'],
  coverageDirectory: 'coverage/persona',
};
