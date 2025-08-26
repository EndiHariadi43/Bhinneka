// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract Bhinneka is ERC20, Ownable {
    constructor() ERC20("Bhinneka", "BHEK") {
        _mint(msg.sender, 1_000_000_000_000 * 10 ** decimals()); // 1 Triliun
    }
}
