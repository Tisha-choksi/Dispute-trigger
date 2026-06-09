import { expect } from "chai";
import { ethers } from "hardhat";
import { Escrow } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("Escrow", function () {
  let escrow: Escrow;
  let buyer: SignerWithAddress;
  let seller: SignerWithAddress;
  let thirdParty: SignerWithAddress;

  beforeEach(async function () {
    [buyer, seller, thirdParty] = await ethers.getSigners();

    const EscrowFactory = await ethers.getContractFactory("Escrow");
    escrow = await EscrowFactory.deploy();
    await escrow.waitForDeployment();
  });

  describe("Escrow Creation", function () {
    it("should create an escrow with correct details", async function () {
      const amount = ethers.parseEther("1.0");

      const tx = await escrow.createEscrow(seller.address, { value: amount });
      await tx.wait();

      const escrowData = await escrow.escrows(1);

      expect(escrowData.buyer).to.equal(buyer.address);
      expect(escrowData.seller).to.equal(seller.address);
      expect(escrowData.amount).to.equal(amount);
      expect(escrowData.released).to.be.false;
      expect(escrowData.disputed).to.be.false;
    });

    it("should reject escrow with zero value", async function () {
      await expect(
        escrow.createEscrow(seller.address, { value: 0 })
      ).to.be.revertedWith("Must send ETH");
    });

    it("should emit EscrowCreated event", async function () {
      const amount = ethers.parseEther("1.0");

      await expect(escrow.createEscrow(seller.address, { value: amount }))
        .to.emit(escrow, "EscrowCreated")
        .withArgs(1, buyer.address, seller.address, amount);
    });

    it("should increment escrow ID", async function () {
      await escrow.createEscrow(seller.address, { value: ethers.parseEther("1") });
      await escrow.createEscrow(seller.address, { value: ethers.parseEther("2") });

      expect(await escrow.nextEscrowId()).to.equal(3);
    });
  });

  describe("Fund Release", function () {
    beforeEach(async function () {
      await escrow.createEscrow(seller.address, { value: ethers.parseEther("1.0") });
    });

    it("should release funds to seller", async function () {
      const sellerBalanceBefore = await ethers.provider.getBalance(seller.address);

      await escrow.releaseFunds(1);

      const sellerBalanceAfter = await ethers.provider.getBalance(seller.address);
      expect(sellerBalanceAfter - sellerBalanceBefore).to.equal(ethers.parseEther("1.0"));

      const escrowData = await escrow.escrows(1);
      expect(escrowData.released).to.be.true;
    });

    it("should only allow buyer to release", async function () {
      await expect(
        escrow.connect(seller).releaseFunds(1)
      ).to.be.revertedWith("Only buyer can release");
    });

    it("should reject double release", async function () {
      await escrow.releaseFunds(1);
      await expect(escrow.releaseFunds(1)).to.be.revertedWith("Already released");
    });

    it("should emit FundsReleased event", async function () {
      await expect(escrow.releaseFunds(1))
        .to.emit(escrow, "FundsReleased")
        .withArgs(1, seller.address, ethers.parseEther("1.0"));
    });
  });

  describe("Dispute Lifecycle", function () {
    beforeEach(async function () {
      await escrow.createEscrow(seller.address, { value: ethers.parseEther("1.0") });
    });

    it("should raise a dispute", async function () {
      await escrow.connect(seller).raiseDispute(1);

      const dispute = await escrow.disputes(1);
      expect(dispute.claimant).to.equal(seller.address);
      expect(dispute.respondent).to.equal(buyer.address);
      expect(dispute.state).to.equal(0); // Open
      expect(dispute.amount).to.equal(ethers.parseEther("1.0"));
    });

    it("should emit DisputeRaised event", async function () {
      await expect(escrow.connect(buyer).raiseDispute(1))
        .to.emit(escrow, "DisputeRaised")
        .withArgs(1, 1, buyer.address, seller.address, ethers.parseEther("1.0"));
    });

    it("should not raise dispute on released escrow", async function () {
      await escrow.releaseFunds(1);
      await expect(escrow.raiseDispute(1)).to.be.revertedWith("Already released");
    });

    it("should not raise dispute twice", async function () {
      await escrow.connect(seller).raiseDispute(1);
      await expect(escrow.connect(buyer).raiseDispute(1)).to.be.revertedWith(
        "Already disputed"
      );
    });

    it("should not allow third party to raise dispute", async function () {
      await expect(
        escrow.connect(thirdParty).raiseDispute(1)
      ).to.be.revertedWith("Not party to escrow");
    });

    it("should submit evidence from claimant", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      const ipfsHash = "QmTest123";

      await escrow.connect(buyer).submitEvidence(1, ipfsHash);

      const dispute = await escrow.disputes(1);
      expect(dispute.evidenceIPFSHashes).to.equal(ipfsHash);
      expect(dispute.state).to.equal(1); // UnderReview
    });

    it("should submit evidence from respondent", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      await escrow.connect(buyer).submitEvidence(1, "QmClaimant1");

      await escrow.connect(seller).submitEvidence(1, "QmRespondent1");

      const dispute = await escrow.disputes(1);
      expect(dispute.evidenceIPFSHashes).to.equal("QmClaimant1,QmRespondent1");
    });

    it("should reject evidence from third party", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      await expect(
        escrow.connect(thirdParty).submitEvidence(1, "QmBad")
      ).to.be.revertedWith("Not party to dispute");
    });

    it("should reject evidence after resolution", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      await escrow.resolveDispute(1, buyer.address);

      await expect(
        escrow.connect(buyer).submitEvidence(1, "QmLate")
      ).to.be.revertedWith("Dispute already resolved");
    });

    it("should emit EvidenceSubmitted event", async function () {
      await escrow.connect(buyer).raiseDispute(1);

      await expect(escrow.connect(buyer).submitEvidence(1, "QmTest"))
        .to.emit(escrow, "EvidenceSubmitted")
        .withArgs(1, buyer.address, "QmTest");
    });

    it("should propose a resolution", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      const cid = "QmRecommendation123";

      await escrow.proposeResolution(1, cid);

      const dispute = await escrow.disputes(1);
      expect(dispute.aiRecommendationCID).to.equal(cid);
    });

    it("should emit ResolutionProposed event", async function () {
      await escrow.connect(buyer).raiseDispute(1);

      await expect(escrow.proposeResolution(1, "QmRec"))
        .to.emit(escrow, "ResolutionProposed")
        .withArgs(1, buyer.address, "QmRec");
    });

    it("should resolve dispute in favor of claimant", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      const expectedAmount = ethers.parseEther("1.0");
      const balanceBefore = await ethers.provider.getBalance(buyer.address);

      const tx = await escrow.resolveDispute(1, buyer.address);
      const receipt = await tx.wait();
      const gasCost = receipt!.gasUsed * receipt!.gasPrice;

      const dispute = await escrow.disputes(1);
      expect(dispute.state).to.equal(2); // Resolved
      expect(dispute.resolvedAt).to.be.gt(0);

      const balanceAfter = await ethers.provider.getBalance(buyer.address);
      expect(balanceAfter - balanceBefore + gasCost).to.equal(expectedAmount);
    });

    it("should resolve dispute in favor of respondent", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      const balanceBefore = await ethers.provider.getBalance(seller.address);

      await escrow.resolveDispute(1, seller.address);

      const balanceAfter = await ethers.provider.getBalance(seller.address);
      expect(balanceAfter - balanceBefore).to.equal(ethers.parseEther("1.0"));
    });

    it("should not resolve with invalid winner", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      await expect(
        escrow.resolveDispute(1, thirdParty.address)
      ).to.be.revertedWith("Invalid winner");
    });

    it("should not resolve twice", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      await escrow.resolveDispute(1, buyer.address);
      await expect(escrow.resolveDispute(1, buyer.address)).to.be.revertedWith(
        "Already resolved"
      );
    });

    it("should emit DisputeResolved event", async function () {
      await escrow.connect(buyer).raiseDispute(1);

      await expect(escrow.resolveDispute(1, buyer.address))
        .to.emit(escrow, "DisputeResolved")
        .withArgs(1, buyer.address, ethers.parseEther("1.0"));
    });

    it("should mark escrow as released after resolution", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      await escrow.resolveDispute(1, buyer.address);

      const escrowData = await escrow.escrows(1);
      expect(escrowData.released).to.be.true;
    });

    it("should handle full flow: create -> dispute -> evidence -> resolve", async function () {
      await escrow.connect(buyer).raiseDispute(1);
      await escrow.connect(buyer).submitEvidence(1, "QmEvidence1");
      await escrow.connect(seller).submitEvidence(1, "QmEvidence2");
      await escrow.proposeResolution(1, "QmRec");
      await escrow.resolveDispute(1, seller.address);

      const dispute = await escrow.disputes(1);
      expect(dispute.state).to.equal(2);
      expect(dispute.evidenceIPFSHashes).to.equal("QmEvidence1,QmEvidence2");
      expect(dispute.aiRecommendationCID).to.equal("QmRec");
    });
  });
});
