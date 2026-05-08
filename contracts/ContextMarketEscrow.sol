// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract ContextMarketEscrow {
    
    IERC20 public usdc;
    address public platform;
    uint256 public platformFeeBps = 1000; // 10%
    
    mapping(bytes32 => bool) public settled;
    mapping(bytes32 => bool) public refunded;
    mapping(bytes32 => uint256) public deposits;
    
    event Deposited(bytes32 indexed queryId, address buyer, uint256 amount);
    event QuerySettled(bytes32 indexed queryId, address seller, uint256 sellerAmount, uint256 platformAmount);
    event Refunded(bytes32 indexed queryId, address buyer, uint256 amount);
    
    event FeeUpdated(uint256 oldFeeBps, uint256 newFeeBps);
    
    constructor(address _usdc, address _platform) {
        usdc = IERC20(_usdc);
        platform = _platform;
    }
    
    function setPlatformFee(uint256 _newFeeBps) external {
        require(msg.sender == platform, "Only platform");
        require(_newFeeBps <= 3000, "Fee max 30%");
        uint256 oldFee = platformFeeBps;
        platformFeeBps = _newFeeBps;
        emit FeeUpdated(oldFee, _newFeeBps);
    }
    
    function deposit(bytes32 queryId, uint256 amount) external {
        require(amount > 0, "Amount must be > 0");
        require(deposits[queryId] == 0, "Already deposited");
        
        bool success = usdc.transferFrom(msg.sender, address(this), amount);
        require(success, "Transfer failed");
        
        deposits[queryId] = amount;
        emit Deposited(queryId, msg.sender, amount);
    }
    
    function settle(bytes32 queryId, address seller) external {
        require(msg.sender == platform, "Only platform");
        require(!settled[queryId], "Already settled");
        require(deposits[queryId] > 0, "No deposit");
        
        uint256 totalAmount = deposits[queryId];
        uint256 platformFee = (totalAmount * platformFeeBps) / 10000;
        uint256 sellerAmount = totalAmount - platformFee;
        
        settled[queryId] = true;
        
        usdc.transfer(seller, sellerAmount);
        usdc.transfer(platform, platformFee);
        
        emit QuerySettled(queryId, seller, sellerAmount, platformFee);
    }
    
    function refund(bytes32 queryId, address buyer, uint256 amount) external {
        require(msg.sender == platform, "Only platform");
        require(!settled[queryId], "Already settled");
        require(!refunded[queryId], "Already refunded");
        require(deposits[queryId] > 0, "No deposit");
        require(amount <= deposits[queryId], "Refund exceeds deposit");
        
        refunded[queryId] = true;
        deposits[queryId] = 0;
        
        usdc.transfer(buyer, amount);
        
        emit Refunded(queryId, buyer, amount);
    }
    
    function getBalance() external view returns (uint256) {
        return usdc.balanceOf(address(this));
    }
}