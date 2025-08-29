// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/*
 * Copyright 2025 Endi Hariadi
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { ERC20 } from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import { ERC20Burnable } from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import { ERC20Pausable } from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import { ERC20Permit } from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { Ownable } from "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title Bhinneka (BHEK)
 * @notice Professional ERC20 token contract intended for EVM chains (Ethereum, BNB Smart Chain, etc.).
 *         Features:
 *           - Fixed supply (all tokens minted at deployment)
 *           - Burnable (holders can burn their tokens)
 *           - Pausable (owner can pause transfers in emergencies)
 *           - EIP‑2612 Permit (gasless approvals)
 *           - Asset recovery helpers (owner can rescue stuck tokens/native coin)
 *
 * @dev This contract uses OpenZeppelin Contracts v5.x.
 *      Constructor mints the full initial supply to a configurable recipient.
 *      No further minting is possible after deployment.
 */
contract Bhinneka is ERC20, ERC20Burnable, ERC20Pausable, ERC20Permit, Ownable {
    /**
     * @notice Deploy the Bhinneka token.
     * @param initialOwner The address that will receive ownership rights.
     * @param initialRecipient The address that will receive the full initial supply.
     * @param initialSupply The initial supply in wei (e.g., 1_000_000 ether for 1M tokens with 18 decimals).
     *
     * @dev Name and symbol are fixed to "Bhinneka" and "BHEK".
     */
    constructor(
        address initialOwner,
        address initialRecipient,
        uint256 initialSupply
    )
        ERC20("Bhinneka", "BHEK")
        ERC20Permit("Bhinneka")
        Ownable(initialOwner)
    {
        require(initialOwner != address(0), "Owner=0");
        require(initialRecipient != address(0), "Recipient=0");
        require(initialSupply > 0, "Supply=0");

        _mint(initialRecipient, initialSupply);
    }

    /* -------------------------------------------------------------------------- */
    /*                                Admin Controls                              */
    /* -------------------------------------------------------------------------- */

    /// @notice Pause all token transfers (emergency circuit breaker).
    function pause() external onlyOwner {
        _pause();
    }

    /// @notice Unpause token transfers.
    function unpause() external onlyOwner {
        _unpause();
    }

    /* -------------------------------------------------------------------------- */
    /*                              Internal Overrides                            */
    /* -------------------------------------------------------------------------- */

    /**
     * @dev Hook required by Solidity for multiple inheritance.
     *      ERC20Pausable overrides _update to enforce pause checks.
     */
    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Pausable)
    {
        super._update(from, to, value);
    }

    /* -------------------------------------------------------------------------- */
    /*                                Asset Rescue                                */
    /* -------------------------------------------------------------------------- */

    /**
     * @notice Recover ERC20 tokens accidentally sent to this contract.
     * @param token The ERC20 token address.
     * @param amount The token amount to recover.
     */
    function recoverERC20(address token, uint256 amount) external onlyOwner {
        IERC20(token).transfer(owner(), amount);
    }

    /**
     * @notice Recover native coin (ETH/BNB/etc.) from this contract.
     * @param amount The amount of native coin to send to the owner.
     */
    function recoverNative(uint256 amount) external onlyOwner {
        (bool ok, ) = payable(owner()).call{value: amount}("");
        require(ok, "Native transfer failed");
    }

    /// @dev Allow receiving native coin.
    receive() external payable {}
}
