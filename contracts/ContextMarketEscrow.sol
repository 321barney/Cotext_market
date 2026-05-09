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
    mapping(bytes32 => uint256) public depositTimestamps;

    bool public paused = false;

    uint256 public constant DEPOSIT_EXPIRATION_DAYS = 30;
    uint256 public constant SECONDS_PER_DAY = 86400;

    event Deposited(bytes32 indexed queryId, address buyer, uint256 amount);
    event QuerySettled(bytes32 indexed queryId, address seller, uint256 sellerAmount, uint256 platformAmount);
    event SettledWithFee(bytes32 indexed queryId, address seller, uint256 sellerAmount, uint256 platformAmount, uint256 feeBps);
    event Refunded(bytes32 indexed queryId, address buyer, uint256 amount);
    event RefundFailed(bytes32 indexed queryId, address buyer, uint256 amount);
    event FeeUpdated(uint256 oldFeeBps, uint256 newFeeBps);
    event Paused(address indexed account);
    event Unpaused(address indexed account);

    modifier whenNotPaused() {
        require(!paused, "Paused");
        _;
    }

    constructor(address _usdc, address _platform) {
        usdc = IERC20(_usdc);
        platform = _platform;
    }

    // ─── SafeTransfer helper (avoids silent failures from non-compliant ERC20s) ───

    function _safeTransfer(IERC20 token, address to, uint256 amount) internal {
        (bool success, bytes memory data) = address(token).call(
            abi.encodeWithSelector(token.transfer.selector, to, amount)
        );
        require(success && (data.length == 0 || abi.decode(data, (bool))), "Transfer failed");
    }

    // ─── Pause / Unpause ───

    function pause() external {
        require(msg.sender == platform, "Only platform");
        require(!paused, "Already paused");
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external {
        require(msg.sender == platform, "Only platform");
        require(paused, "Not paused");
        paused = false;
        emit Unpaused(msg.sender);
    }

    // ─── Platform Fee Management ───

    function setPlatformFee(uint256 _newFeeBps) external {
        require(msg.sender == platform, "Only platform");
        require(_newFeeBps <= 3000, "Fee max 30%");
        uint256 oldFee = platformFeeBps;
        platformFeeBps = _newFeeBps;
        emit FeeUpdated(oldFee, _newFeeBps);
    }

    /**
     * @notice Returns the current maximum platform fee (in basis points).
     *         The backend can query this to calculate a seller's tiered fee.
     */
    function getPlatformFee() external view returns (uint256) {
        return platformFeeBps;
    }

    // ─── Deposit ───

    function deposit(bytes32 queryId, uint256 amount) external whenNotPaused {
        require(amount > 0, "Amount must be > 0");
        require(deposits[queryId] == 0, "Already deposited");

        bool success = usdc.transferFrom(msg.sender, address(this), amount);
        require(success, "Transfer failed");

        deposits[queryId] = amount;
        depositTimestamps[queryId] = block.timestamp;
        emit Deposited(queryId, msg.sender, amount);
    }

    // ─── Settle ───

    /**
     * @notice Settles an escrowed query by splitting the deposit between seller and platform.
     * @param queryId The unique identifier for the escrowed query.
     * @param seller  The address that will receive the seller's share.
     * @param feeBps  The actual fee in basis points to apply. Must be <= platformFeeBps.
     *
     * The backend passes a tiered fee (e.g. 700 for a 7% platinum seller).
     * The contract enforces that feeBps never exceeds platformFeeBps (the cap).
     */
    function settle(bytes32 queryId, address seller, uint256 feeBps) external whenNotPaused {
        require(msg.sender == platform, "Only platform");
        require(!settled[queryId], "Already settled");
        require(deposits[queryId] > 0, "No deposit");
        require(feeBps <= platformFeeBps, "Fee exceeds max");

        uint256 totalAmount = deposits[queryId];
        uint256 platformFee = (totalAmount * feeBps) / 10000;
        uint256 sellerAmount = totalAmount - platformFee;

        settled[queryId] = true;
        deposits[queryId] = 0;
        delete depositTimestamps[queryId];

        _safeTransfer(usdc, seller, sellerAmount);
        _safeTransfer(usdc, platform, platformFee);

        emit QuerySettled(queryId, seller, sellerAmount, platformFee);
        emit SettledWithFee(queryId, seller, sellerAmount, platformFee, feeBps);
    }

    /**
     * @notice Backward-compatible settle using the full platformFeeBps as the fee.
     *         Kept for ABI compatibility with existing integrations.
     */
    function settle(bytes32 queryId, address seller) external whenNotPaused {
        this.settle(queryId, seller, platformFeeBps);
    }

    // ─── Refund ───

    function refund(bytes32 queryId, address buyer, uint256 amount) external whenNotPaused {
        require(msg.sender == platform, "Only platform");
        require(!settled[queryId], "Already settled");
        require(!refunded[queryId], "Already refunded");
        require(deposits[queryId] > 0, "No deposit");
        require(amount <= deposits[queryId], "Refund exceeds deposit");

        refunded[queryId] = true;
        deposits[queryId] = 0;
        delete depositTimestamps[queryId];

        _safeTransfer(usdc, buyer, amount);

        emit Refunded(queryId, buyer, amount);
    }

    /**
     * @notice Emergency refund for deposits older than 30 days.
     *         Bypasses the 'already settled/refunded' checks.
     */
    function emergencyRefund(bytes32 queryId, address buyer, uint256 amount) external {
        require(msg.sender == platform, "Only platform");
        require(deposits[queryId] > 0, "No deposit");
        require(
            block.timestamp > depositTimestamps[queryId] + (DEPOSIT_EXPIRATION_DAYS * SECONDS_PER_DAY),
            "Deposit not expired"
        );
        require(amount <= deposits[queryId], "Refund exceeds deposit");

        deposits[queryId] = 0;
        delete depositTimestamps[queryId];

        _safeTransfer(usdc, buyer, amount);

        emit Refunded(queryId, buyer, amount);
    }

    // ─── Emergency Settle (for expired deposits) ───

    /**
     * @notice Emergency settle for deposits older than 30 days.
     *         Bypasses the 'already settled/refunded' checks.
     */
    function emergencySettle(bytes32 queryId, address seller, uint256 feeBps) external {
        require(msg.sender == platform, "Only platform");
        require(deposits[queryId] > 0, "No deposit");
        require(feeBps <= platformFeeBps, "Fee exceeds max");
        require(
            block.timestamp > depositTimestamps[queryId] + (DEPOSIT_EXPIRATION_DAYS * SECONDS_PER_DAY),
            "Deposit not expired"
        );

        uint256 totalAmount = deposits[queryId];
        uint256 platformFee = (totalAmount * feeBps) / 10000;
        uint256 sellerAmount = totalAmount - platformFee;

        deposits[queryId] = 0;
        delete depositTimestamps[queryId];

        _safeTransfer(usdc, seller, sellerAmount);
        _safeTransfer(usdc, platform, platformFee);

        emit QuerySettled(queryId, seller, sellerAmount, platformFee);
        emit SettledWithFee(queryId, seller, sellerAmount, platformFee, feeBps);
    }

    // ─── View Functions ───

    function getBalance() external view returns (uint256) {
        return usdc.balanceOf(address(this));
    }

    /**
     * @notice Returns whether a deposit has expired (older than 30 days).
     */
    function isDepositExpired(bytes32 queryId) external view returns (bool) {
        return
            depositTimestamps[queryId] > 0 &&
            block.timestamp > depositTimestamps[queryId] + (DEPOSIT_EXPIRATION_DAYS * SECONDS_PER_DAY);
    }

    /**
     * @notice Returns the timestamp when a deposit was made.
     */
    function getDepositTimestamp(bytes32 queryId) external view returns (uint256) {
        return depositTimestamps[queryId];
    }
}
