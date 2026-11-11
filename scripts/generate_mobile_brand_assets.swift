import AppKit
import Foundation
import ImageIO
import UniformTypeIdentifiers

// The supplied SVGs wrap original PNG artwork; retain those pixels without redrawing the logo.
let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let mobile = root.appendingPathComponent("apps/mobile")
let source = root.appendingPathComponent("apps/web_django/static/images")
let assets = mobile.appendingPathComponent("assets/images")
for name in ["logo", "landscape_logo_with_name", "portrait_logo_with_name"] {
    let svg = try String(contentsOf: source.appendingPathComponent("\(name).svg"), encoding: .utf8)
    let expression = try NSRegularExpression(pattern: "data:image/png;base64,([^\"]+)")
    guard let match = expression.firstMatch(in: svg, range: NSRange(svg.startIndex..., in: svg)),
          let range = Range(match.range(at: 1), in: svg),
          let data = Data(base64Encoded: String(svg[range])) else {
        fatalError("Missing embedded PNG artwork in \(name).svg")
    }
    try data.write(to: assets.appendingPathComponent("\(name).png"))
}

guard let logo = NSImage(contentsOf: assets.appendingPathComponent("logo.png")) else {
    fatalError("Cannot decode supplied logo")
}
func icon(_ size: Int, at destination: URL) throws {
    guard let bitmap = CGContext(
        data: nil, width: size, height: size, bitsPerComponent: 8,
        bytesPerRow: size * 4, space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
    ) else {
        fatalError("Cannot allocate icon bitmap")
    }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(cgContext: bitmap, flipped: false)
    NSColor.white.setFill()
    NSRect(x: 0, y: 0, width: size, height: size).fill()
    let height = CGFloat(size) * 0.8
    let width = height * logo.size.width / logo.size.height
    NSGraphicsContext.current?.imageInterpolation = .high
    logo.draw(in: NSRect(x: (CGFloat(size) - width) / 2,
                        y: (CGFloat(size) - height) / 2, width: width, height: height))
    NSGraphicsContext.restoreGraphicsState()
    guard let image = bitmap.makeImage(),
          let output = CGImageDestinationCreateWithURL(destination as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        fatalError("Cannot encode icon")
    }
    CGImageDestinationAddImage(output, image, nil)
    guard CGImageDestinationFinalize(output) else { fatalError("Cannot save icon") }
}

let ios = mobile.appendingPathComponent("ios/Runner/Assets.xcassets/AppIcon.appiconset")
let contents = try JSONSerialization.jsonObject(with: Data(contentsOf: ios.appendingPathComponent("Contents.json")))
guard let catalog = contents as? [String: Any], let images = catalog["images"] as? [[String: String]] else {
    fatalError("Invalid iOS icon catalog")
}
for entry in images {
    guard let filename = entry["filename"], let dimension = entry["size"]?.components(separatedBy: "x").first,
          let points = Double(dimension), let scaleText = entry["scale"],
          let scale = Double(scaleText.replacingOccurrences(of: "x", with: "")) else {
        fatalError("Invalid iOS icon entry")
    }
    try icon(Int(points * scale), at: ios.appendingPathComponent(filename))
}
for (density, size) in ["mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192] {
    try icon(size, at: mobile.appendingPathComponent("android/app/src/main/res/mipmap-\(density)/ic_launcher.png"))
}
print("Generated mobile artwork and opaque iOS/Android launcher icons from supplied originals.")
