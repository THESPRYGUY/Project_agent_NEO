module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests/js'],
  moduleNameMapper: {
    '^src/persona/(.*)$': '<rootDir>/src/persona/$1',
    '^src/naics/(.*)$': '<rootDir>/src/naics/$1',
    '^src/ui/(.*)$': '<rootDir>/src/ui/$1',
  },
  collectCoverageFrom: ['src/persona/**/*.ts','src/naics/**/*.ts'],
  coverageDirectory: 'coverage/all',
};
