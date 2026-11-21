import Foundation
import Vision
import Darwin

struct Span: Encodable {
    let text: String
    let box: [CGFloat]
    let confidence: Float
}

do {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    // Latin-script form: keeps Vision from returning Cyrillic/Greek look-alikes (e.g. U+041C for M).
    request.recognitionLanguages = ["en-US", "fr-FR", "de-DE", "it-IT"]
    let data = FileHandle.standardInput.readDataToEndOfFile()
    try VNImageRequestHandler(data: data).perform([request])
    let spans = (request.results ?? []).compactMap { observation -> Span? in
        guard let match = observation.topCandidates(1).first else { return nil }
        let b = observation.boundingBox
        return Span(text: match.string, box: [b.minX, 1-b.maxY, b.maxX, 1-b.minY], confidence: match.confidence)
    }
    FileHandle.standardOutput.write(try JSONEncoder().encode(spans))
} catch {
    FileHandle.standardError.write(Data(error.localizedDescription.utf8))
    exit(1)
}
