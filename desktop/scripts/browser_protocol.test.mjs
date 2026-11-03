import { describe, expect, it } from "vitest";
import { Cdp, evaluateWithArguments } from "./browser_e2e.mjs";

describe("local browser test protocol", () => {
  it("rejects remote and credential-bearing debugger endpoints", () => {
    for (const endpoint of ["wss://example.org/devtools/page/test", "ws://example.org/devtools/page/test",
      "ws://user:password@127.0.0.1:9222/devtools/page/test", "ws://127.0.0.1:9222/other"]) {
      expect(() => new Cdp(endpoint)).toThrow("local Chrome");
    }
    expect(new Cdp("ws://127.0.0.1:9222/devtools/page/test").url).toContain("127.0.0.1");
  });

  it("passes quotes and executable-looking input as data and releases remote handles", async () => {
    const calls=[];
    const cdp={send:async(method,params)=>{
      calls.push({method,params});
      return method === "Runtime.evaluate" ? {result:{objectId:"window"}} : {result:{value:true}};
    }};
    const input='\"); globalThis.untrustedExecuted=true; ("';
    expect(await evaluateWithArguments(cdp,(value)=>value,input)).toBe(true);
    const call=calls.find(item=>item.method === "Runtime.callFunctionOn");
    expect(call.params.functionDeclaration).not.toContain(input);
    expect(call.params.arguments).toEqual([{value:input}]);
    expect(calls.at(-1).method).toBe("Runtime.releaseObjectGroup");
  });
});
