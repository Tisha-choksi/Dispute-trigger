// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract Escrow {
    enum DisputeState { Open, UnderReview, Resolved }

    struct EscrowAgreement {
        uint256 id;
        address buyer;
        address seller;
        uint256 amount;
        bool released;
        bool disputed;
        uint256 disputeId;
    }

    struct Dispute {
        uint256 id;
        address claimant;
        address respondent;
        uint256 amount;
        DisputeState state;
        string evidenceIPFSHashes;
        string aiSummaryCID;
        string aiRecommendationCID;
        address resolver;
        uint256 createdAt;
        uint256 resolvedAt;
    }

    uint256 public nextEscrowId = 1;
    uint256 public nextDisputeId = 1;

    mapping(uint256 => EscrowAgreement) public escrows;
    mapping(uint256 => Dispute) public disputes;
    mapping(uint256 => uint256) public disputeToEscrow;

    event EscrowCreated(
        uint256 indexed escrowId,
        address indexed buyer,
        address indexed seller,
        uint256 amount
    );

    event FundsReleased(
        uint256 indexed escrowId,
        address indexed recipient,
        uint256 amount
    );

    event DisputeRaised(
        uint256 indexed disputeId,
        uint256 indexed escrowId,
        address indexed claimant,
        address respondent,
        uint256 amount
    );

    event EvidenceSubmitted(
        uint256 indexed disputeId,
        address indexed submitter,
        string ipfsHash
    );

    event ResolutionProposed(
        uint256 indexed disputeId,
        address indexed resolver,
        string recommendationCID
    );

    event DisputeResolved(
        uint256 indexed disputeId,
        address indexed winner,
        uint256 payout
    );

    function createEscrow(address _seller) external payable {
        require(msg.value > 0, "Must send ETH");

        escrows[nextEscrowId] = EscrowAgreement({
            id: nextEscrowId,
            buyer: msg.sender,
            seller: _seller,
            amount: msg.value,
            released: false,
            disputed: false,
            disputeId: 0
        });

        emit EscrowCreated(nextEscrowId, msg.sender, _seller, msg.value);
        nextEscrowId++;
    }

    function releaseFunds(uint256 _escrowId) external {
        EscrowAgreement storage escrow = escrows[_escrowId];
        require(msg.sender == escrow.buyer, "Only buyer can release");
        require(!escrow.released, "Already released");
        require(!escrow.disputed, "Dispute active");

        escrow.released = true;
        payable(escrow.seller).transfer(escrow.amount);

        emit FundsReleased(_escrowId, escrow.seller, escrow.amount);
    }

    function raiseDispute(uint256 _escrowId) external {
        EscrowAgreement storage escrow = escrows[_escrowId];
        require(
            msg.sender == escrow.buyer || msg.sender == escrow.seller,
            "Not party to escrow"
        );
        require(!escrow.released, "Already released");
        require(!escrow.disputed, "Already disputed");

        escrow.disputed = true;

        address claimant = msg.sender;
        address respondent = (claimant == escrow.buyer)
            ? escrow.seller
            : escrow.buyer;

        uint256 disputeId = nextDisputeId;
        disputes[disputeId] = Dispute({
            id: disputeId,
            claimant: claimant,
            respondent: respondent,
            amount: escrow.amount,
            state: DisputeState.Open,
            evidenceIPFSHashes: "",
            aiSummaryCID: "",
            aiRecommendationCID: "",
            resolver: address(0),
            createdAt: block.timestamp,
            resolvedAt: 0
        });

        disputeToEscrow[disputeId] = _escrowId;
        escrow.disputeId = disputeId;

        emit DisputeRaised(disputeId, _escrowId, claimant, respondent, escrow.amount);
        nextDisputeId++;
    }

    function submitEvidence(uint256 _disputeId, string calldata _ipfsHash) external {
        Dispute storage dispute = disputes[_disputeId];
        require(
            msg.sender == dispute.claimant || msg.sender == dispute.respondent,
            "Not party to dispute"
        );
        require(dispute.state != DisputeState.Resolved, "Dispute already resolved");

        if (bytes(dispute.evidenceIPFSHashes).length > 0) {
            dispute.evidenceIPFSHashes = string(
                abi.encodePacked(dispute.evidenceIPFSHashes, ",", _ipfsHash)
            );
        } else {
            dispute.evidenceIPFSHashes = _ipfsHash;
        }

        if (dispute.state == DisputeState.Open) {
            dispute.state = DisputeState.UnderReview;
        }

        emit EvidenceSubmitted(_disputeId, msg.sender, _ipfsHash);
    }

    function proposeResolution(
        uint256 _disputeId,
        string calldata _recommendationCID
    ) external {
        Dispute storage dispute = disputes[_disputeId];
        require(dispute.state != DisputeState.Resolved, "Already resolved");

        dispute.aiRecommendationCID = _recommendationCID;
        dispute.resolver = msg.sender;

        emit ResolutionProposed(_disputeId, msg.sender, _recommendationCID);
    }

    function resolveDispute(uint256 _disputeId, address _winner) external {
        Dispute storage dispute = disputes[_disputeId];
        require(dispute.state != DisputeState.Resolved, "Already resolved");
        require(
            _winner == dispute.claimant || _winner == dispute.respondent,
            "Invalid winner"
        );

        dispute.state = DisputeState.Resolved;
        dispute.resolvedAt = block.timestamp;

        uint256 escrowId = disputeToEscrow[_disputeId];
        EscrowAgreement storage escrow = escrows[escrowId];
        escrow.released = true;

        payable(_winner).transfer(dispute.amount);

        emit DisputeResolved(_disputeId, _winner, dispute.amount);
    }
}
