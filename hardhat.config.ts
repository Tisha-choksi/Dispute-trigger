import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    localhost: { url: "http://127.0.0.1:8545" },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
  },
};

//Speoholia server configuration

export default config;
