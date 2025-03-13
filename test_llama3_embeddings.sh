#!/bin/bash

# Script to test Llama3 embeddings with different chunk sizes

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo "Error: Ollama is not running. Please start it first."
    exit 1
fi

# Create test document with legal text
cat > test_data/test_legal_document.txt << EOT
IN THE UNITED STATES DISTRICT COURT
FOR THE DISTRICT OF COLUMBIA

UNITED STATES OF AMERICA,
Plaintiff,
v.
JOHN DOE,
Defendant.

MEMORANDUM OPINION

This matter comes before the Court on Defendant's Motion to Dismiss. After careful consideration of the parties' submissions, the relevant legal authorities, and the entire record, the Court DENIES the motion for the reasons set forth below.

I. BACKGROUND

On January 1, 2025, Defendant John Doe was charged with violating 18 U.S.C. § 1343 (wire fraud) and 18 U.S.C. § 1956 (money laundering). The indictment alleges that between March 2024 and December 2024, Defendant engaged in a scheme to defraud investors by soliciting investments in a fictitious cryptocurrency platform.

According to the Government, Defendant raised approximately $10 million from investors by falsely representing that their funds would be used to develop a revolutionary blockchain technology. Instead, the Government alleges that Defendant diverted a substantial portion of the funds for personal expenses, including the purchase of luxury vehicles, real estate, and travel.

On February 15, 2025, Defendant filed the instant Motion to Dismiss, arguing that: (1) the indictment fails to state an offense; (2) the wire fraud statute is unconstitutionally vague as applied to cryptocurrency transactions; and (3) the Government engaged in selective prosecution.

II. LEGAL STANDARD

Federal Rule of Criminal Procedure 12(b)(3)(B)(v) permits a defendant to file a pretrial motion to dismiss an indictment for "failure to state an offense." To withstand a motion to dismiss, an indictment must "contain[] the elements of the offense charged and fairly inform[] a defendant of the charge against which he must defend." Hamling v. United States, 418 U.S. 87, 117 (1974). The Court must presume the allegations in the indictment to be true. United States v. Ballestas, 795 F.3d 138, 149 (D.C. Cir. 2015).

A statute is unconstitutionally vague if it "fails to give ordinary people fair notice of the conduct it punishes, or [is] so standardless that it invites arbitrary enforcement." Johnson v. United States, 576 U.S. 591, 595 (2015). To establish selective prosecution, a defendant must demonstrate that the prosecution "had a discriminatory effect and that it was motivated by a discriminatory purpose." United States v. Armstrong, 517 U.S. 456, 465 (1996).

III. ANALYSIS

A. Sufficiency of the Indictment

Defendant first argues that the indictment fails to state an offense because it does not allege specific misrepresentations made to investors. This argument lacks merit. The indictment clearly alleges that Defendant made false statements regarding the use of investor funds, specifically that the funds would be used to develop blockchain technology when, in fact, Defendant diverted a substantial portion for personal expenses.

The elements of wire fraud under 18 U.S.C. § 1343 are: (1) a scheme to defraud; (2) the use of interstate wire communications to further the scheme; and (3) specific intent to defraud. United States v. Maxwell, 920 F.2d 1028, 1035 (D.C. Cir. 1990). The indictment alleges each of these elements, stating that Defendant devised a scheme to defraud investors, used interstate wire communications (including emails and wire transfers) to execute the scheme, and acted with intent to defraud.

Similarly, the indictment properly alleges the elements of money laundering under 18 U.S.C. § 1956, including that Defendant conducted financial transactions involving proceeds of specified unlawful activity with the intent to conceal the source of the proceeds.

B. Vagueness Challenge

Defendant's argument that the wire fraud statute is unconstitutionally vague as applied to cryptocurrency transactions is without merit. The wire fraud statute prohibits "any scheme or artifice to defraud, or for obtaining money or property by means of false or fraudulent pretenses, representations, or promises" using interstate wire communications. 18 U.S.C. § 1343. This language provides clear notice that fraudulent schemes involving false representations to obtain money, regardless of whether cryptocurrency is involved, fall within the statute's prohibition.

Courts have consistently applied the wire fraud statute to new technologies and forms of fraud. See, e.g., United States v. Carpenter, 484 U.S. 19, 25 (1987) (applying mail and wire fraud statutes to novel fraud involving confidential information). The fact that the alleged scheme involved cryptocurrency does not render the statute vague. The core conduct prohibited—making false representations to obtain money—is clearly defined.

C. Selective Prosecution

Finally, Defendant's selective prosecution claim fails because he has not provided "clear evidence" of discriminatory effect and purpose. Armstrong, 517 U.S. at 465. Defendant merely alleges that other cryptocurrency entrepreneurs have engaged in similar conduct without facing prosecution. This bare assertion, without specific examples or evidence of discriminatory intent, is insufficient to overcome the "presumption of regularity" that attaches to prosecutorial decisions. Id. at 464.

IV. CONCLUSION

For the foregoing reasons, Defendant's Motion to Dismiss is DENIED. An appropriate Order accompanies this Memorandum Opinion.

SO ORDERED.

Dated: March 15, 2025
Washington, D.C.

JANE SMITH
United States District Judge
EOT

# Run the test script with different chunk sizes
echo "Running tests with different chunk sizes..."
python3 scripts/test_llama3_embeddings.py --file test_data/test_legal_document.txt --output test_data/llama3_embedding_results.json

echo "Test completed! Results saved to test_data/llama3_embedding_results.json"
