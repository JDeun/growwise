import { describe, expect, it } from "vitest";

import { parseDiscoveryLocation } from "./discovery-api";

describe("parseDiscoveryLocation", () => {
  it("returns null when no location is supplied", () => {
    expect(parseDiscoveryLocation("", " ")).toBeNull();
  });

  it("accepts an explicit coordinate pair", () => {
    expect(parseDiscoveryLocation("37.2636", "127.0286")).toEqual({
      latitude: 37.2636,
      longitude: 127.0286,
    });
  });

  it("requires latitude and longitude together", () => {
    expect(() => parseDiscoveryLocation("37.2", "")).toThrow("함께 입력");
    expect(() => parseDiscoveryLocation("", "127.0")).toThrow("함께 입력");
  });

  it("rejects coordinates outside geographic bounds", () => {
    expect(() => parseDiscoveryLocation("91", "127")).toThrow("위도");
    expect(() => parseDiscoveryLocation("37", "181")).toThrow("경도");
  });
});
