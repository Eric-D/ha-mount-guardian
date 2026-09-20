/* mount-guard-card — artefact de build, ne pas éditer directement. Sources : frontend/src/ */
var de=Object.defineProperty;var ue=Object.getOwnPropertyDescriptor;var C=(r,t,e,s)=>{for(var n=s>1?void 0:s?ue(t,e):t,o=r.length-1,i;o>=0;o--)(i=r[o])&&(n=(s?i(t,e,n):i(n))||n);return s&&n&&de(t,e,n),n};var Y=globalThis,J=Y.ShadowRoot&&(Y.ShadyCSS===void 0||Y.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ct=Symbol(),xt=new WeakMap,P=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==ct)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(J&&t===void 0){let s=e!==void 0&&e.length===1;s&&(t=xt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),s&&xt.set(e,t))}return t}toString(){return this.cssText}},St=r=>new P(typeof r=="string"?r:r+"",void 0,ct),L=(r,...t)=>{let e=r.length===1?r[0]:t.reduce((s,n,o)=>s+(i=>{if(i._$cssResult$===!0)return i.cssText;if(typeof i=="number")return i;throw Error("Value passed to 'css' function must be a 'css' function result: "+i+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(n)+r[o+1],r[0]);return new P(e,r,ct)},At=(r,t)=>{if(J)r.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let s=document.createElement("style"),n=Y.litNonce;n!==void 0&&s.setAttribute("nonce",n),s.textContent=e.cssText,r.appendChild(s)}},dt=J?r=>r:r=>r instanceof CSSStyleSheet?(t=>{let e="";for(let s of t.cssRules)e+=s.cssText;return St(e)})(r):r;var{is:pe,defineProperty:he,getOwnPropertyDescriptor:me,getOwnPropertyNames:fe,getOwnPropertySymbols:ge,getPrototypeOf:ye}=Object,v=globalThis,wt=v.trustedTypes,_e=wt?wt.emptyScript:"",ve=v.reactiveElementPolyfillSupport,U=(r,t)=>r,H={toAttribute(r,t){switch(t){case Boolean:r=r?_e:null;break;case Object:case Array:r=r==null?r:JSON.stringify(r)}return r},fromAttribute(r,t){let e=r;switch(t){case Boolean:e=r!==null;break;case Number:e=r===null?null:Number(r);break;case Object:case Array:try{e=JSON.parse(r)}catch{e=null}}return e}},X=(r,t)=>!pe(r,t),Et={attribute:!0,type:String,converter:H,reflect:!1,useDefault:!1,hasChanged:X};Symbol.metadata??(Symbol.metadata=Symbol("metadata")),v.litPropertyMetadata??(v.litPropertyMetadata=new WeakMap);var y=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??(this.l=[])).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Et){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let s=Symbol(),n=this.getPropertyDescriptor(t,s,e);n!==void 0&&he(this.prototype,t,n)}}static getPropertyDescriptor(t,e,s){let{get:n,set:o}=me(this.prototype,t)??{get(){return this[e]},set(i){this[e]=i}};return{get:n,set(i){let l=n?.call(this);o?.call(this,i),this.requestUpdate(t,l,s)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Et}static _$Ei(){if(this.hasOwnProperty(U("elementProperties")))return;let t=ye(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(U("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(U("properties"))){let e=this.properties,s=[...fe(e),...ge(e)];for(let n of s)this.createProperty(n,e[n])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[s,n]of e)this.elementProperties.set(s,n)}this._$Eh=new Map;for(let[e,s]of this.elementProperties){let n=this._$Eu(e,s);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let s=new Set(t.flat(1/0).reverse());for(let n of s)e.unshift(dt(n))}else t!==void 0&&e.push(dt(t));return e}static _$Eu(t,e){let s=e.attribute;return s===!1?void 0:typeof s=="string"?s:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??(this._$EO=new Set)).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let s of e.keys())this.hasOwnProperty(s)&&(t.set(s,this[s]),delete this[s]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return At(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??(this.renderRoot=this.createRenderRoot()),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,s){this._$AK(t,s)}_$ET(t,e){let s=this.constructor.elementProperties.get(t),n=this.constructor._$Eu(t,s);if(n!==void 0&&s.reflect===!0){let o=(s.converter?.toAttribute!==void 0?s.converter:H).toAttribute(e,s.type);this._$Em=t,o==null?this.removeAttribute(n):this.setAttribute(n,o),this._$Em=null}}_$AK(t,e){let s=this.constructor,n=s._$Eh.get(t);if(n!==void 0&&this._$Em!==n){let o=s.getPropertyOptions(n),i=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:H;this._$Em=n;let l=i.fromAttribute(e,o.type);this[n]=l??this._$Ej?.get(n)??l,this._$Em=null}}requestUpdate(t,e,s,n=!1,o){if(t!==void 0){let i=this.constructor;if(n===!1&&(o=this[t]),s??(s=i.getPropertyOptions(t)),!((s.hasChanged??X)(o,e)||s.useDefault&&s.reflect&&o===this._$Ej?.get(t)&&!this.hasAttribute(i._$Eu(t,s))))return;this.C(t,e,s)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:s,reflect:n,wrapped:o},i){s&&!(this._$Ej??(this._$Ej=new Map)).has(t)&&(this._$Ej.set(t,i??e??this[t]),o!==!0||i!==void 0)||(this._$AL.has(t)||(this.hasUpdated||s||(e=void 0),this._$AL.set(t,e)),n===!0&&this._$Em!==t&&(this._$Eq??(this._$Eq=new Set)).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??(this.renderRoot=this.createRenderRoot()),this._$Ep){for(let[n,o]of this._$Ep)this[n]=o;this._$Ep=void 0}let s=this.constructor.elementProperties;if(s.size>0)for(let[n,o]of s){let{wrapped:i}=o,l=this[n];i!==!0||this._$AL.has(n)||l===void 0||this.C(n,void 0,o,l)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(s=>s.hostUpdate?.()),this.update(e)):this._$EM()}catch(s){throw t=!1,this._$EM(),s}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&(this._$Eq=this._$Eq.forEach(e=>this._$ET(e,this[e]))),this._$EM()}updated(t){}firstUpdated(t){}};y.elementStyles=[],y.shadowRootOptions={mode:"open"},y[U("elementProperties")]=new Map,y[U("finalized")]=new Map,ve?.({ReactiveElement:y}),(v.reactiveElementVersions??(v.reactiveElementVersions=[])).push("2.1.2");var N=globalThis,Rt=r=>r,Q=N.trustedTypes,Ct=Q?Q.createPolicy("lit-html",{createHTML:r=>r}):void 0,Ut="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,Ht="?"+b,be=`<${Ht}>`,S=document,D=()=>S.createComment(""),j=r=>r===null||typeof r!="object"&&typeof r!="function",yt=Array.isArray,$e=r=>yt(r)||typeof r?.[Symbol.iterator]=="function",ut=`[ 	
\f\r]`,O=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Tt=/-->/g,kt=/>/g,$=RegExp(`>|${ut}(?:([^\\s"'>=/]+)(${ut}*=${ut}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Mt=/'/g,Pt=/"/g,Ot=/^(?:script|style|textarea|title)$/i,_t=r=>(t,...e)=>({_$litType$:r,strings:t,values:e}),u=_t(1),Ye=_t(2),Je=_t(3),A=Symbol.for("lit-noChange"),p=Symbol.for("lit-nothing"),Lt=new WeakMap,x=S.createTreeWalker(S,129);function Nt(r,t){if(!yt(r)||!r.hasOwnProperty("raw"))throw Error("invalid template strings array");return Ct!==void 0?Ct.createHTML(t):t}var xe=(r,t)=>{let e=r.length-1,s=[],n,o=t===2?"<svg>":t===3?"<math>":"",i=O;for(let l=0;l<e;l++){let a=r[l],c,h,d=-1,g=0;for(;g<a.length&&(i.lastIndex=g,h=i.exec(a),h!==null);)g=i.lastIndex,i===O?h[1]==="!--"?i=Tt:h[1]!==void 0?i=kt:h[2]!==void 0?(Ot.test(h[2])&&(n=RegExp("</"+h[2],"g")),i=$):h[3]!==void 0&&(i=$):i===$?h[0]===">"?(i=n??O,d=-1):h[1]===void 0?d=-2:(d=i.lastIndex-h[2].length,c=h[1],i=h[3]===void 0?$:h[3]==='"'?Pt:Mt):i===Pt||i===Mt?i=$:i===Tt||i===kt?i=O:(i=$,n=void 0);let _=i===$&&r[l+1].startsWith("/>")?" ":"";o+=i===O?a+be:d>=0?(s.push(c),a.slice(0,d)+Ut+a.slice(d)+b+_):a+b+(d===-2?l:_)}return[Nt(r,o+(r[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),s]},q=class r{constructor({strings:t,_$litType$:e},s){let n;this.parts=[];let o=0,i=0,l=t.length-1,a=this.parts,[c,h]=xe(t,e);if(this.el=r.createElement(c,s),x.currentNode=this.el.content,e===2||e===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(n=x.nextNode())!==null&&a.length<l;){if(n.nodeType===1){if(n.hasAttributes())for(let d of n.getAttributeNames())if(d.endsWith(Ut)){let g=h[i++],_=n.getAttribute(d).split(b),K=/([.?@])?(.*)/.exec(g);a.push({type:1,index:o,name:K[2],strings:_,ctor:K[1]==="."?ht:K[1]==="?"?mt:K[1]==="@"?ft:k}),n.removeAttribute(d)}else d.startsWith(b)&&(a.push({type:6,index:o}),n.removeAttribute(d));if(Ot.test(n.tagName)){let d=n.textContent.split(b),g=d.length-1;if(g>0){n.textContent=Q?Q.emptyScript:"";for(let _=0;_<g;_++)n.append(d[_],D()),x.nextNode(),a.push({type:2,index:++o});n.append(d[g],D())}}}else if(n.nodeType===8)if(n.data===Ht)a.push({type:2,index:o});else{let d=-1;for(;(d=n.data.indexOf(b,d+1))!==-1;)a.push({type:7,index:o}),d+=b.length-1}o++}}static createElement(t,e){let s=S.createElement("template");return s.innerHTML=t,s}};function T(r,t,e=r,s){if(t===A)return t;let n=s!==void 0?e._$Co?.[s]:e._$Cl,o=j(t)?void 0:t._$litDirective$;return n?.constructor!==o&&(n?._$AO?.(!1),o===void 0?n=void 0:(n=new o(r),n._$AT(r,e,s)),s!==void 0?(e._$Co??(e._$Co=[]))[s]=n:e._$Cl=n),n!==void 0&&(t=T(r,n._$AS(r,t.values),n,s)),t}var pt=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:s}=this._$AD,n=(t?.creationScope??S).importNode(e,!0);x.currentNode=n;let o=x.nextNode(),i=0,l=0,a=s[0];for(;a!==void 0;){if(i===a.index){let c;a.type===2?c=new I(o,o.nextSibling,this,t):a.type===1?c=new a.ctor(o,a.name,a.strings,this,t):a.type===6&&(c=new gt(o,this,t)),this._$AV.push(c),a=s[++l]}i!==a?.index&&(o=x.nextNode(),i++)}return x.currentNode=S,n}p(t){let e=0;for(let s of this._$AV)s!==void 0&&(s.strings!==void 0?(s._$AI(t,s,e),e+=s.strings.length-2):s._$AI(t[e])),e++}},I=class r{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,s,n){this.type=2,this._$AH=p,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=s,this.options=n,this._$Cv=n?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=T(this,t,e),j(t)?t===p||t==null||t===""?(this._$AH!==p&&this._$AR(),this._$AH=p):t!==this._$AH&&t!==A&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):$e(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==p&&j(this._$AH)?this._$AA.nextSibling.data=t:this.T(S.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:s}=t,n=typeof s=="number"?this._$AC(t):(s.el===void 0&&(s.el=q.createElement(Nt(s.h,s.h[0]),this.options)),s);if(this._$AH?._$AD===n)this._$AH.p(e);else{let o=new pt(n,this),i=o.u(this.options);o.p(e),this.T(i),this._$AH=o}}_$AC(t){let e=Lt.get(t.strings);return e===void 0&&Lt.set(t.strings,e=new q(t)),e}k(t){yt(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,s,n=0;for(let o of t)n===e.length?e.push(s=new r(this.O(D()),this.O(D()),this,this.options)):s=e[n],s._$AI(o),n++;n<e.length&&(this._$AR(s&&s._$AB.nextSibling,n),e.length=n)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let s=Rt(t).nextSibling;Rt(t).remove(),t=s}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},k=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,s,n,o){this.type=1,this._$AH=p,this._$AN=void 0,this.element=t,this.name=e,this._$AM=n,this.options=o,s.length>2||s[0]!==""||s[1]!==""?(this._$AH=Array(s.length-1).fill(new String),this.strings=s):this._$AH=p}_$AI(t,e=this,s,n){let o=this.strings,i=!1;if(o===void 0)t=T(this,t,e,0),i=!j(t)||t!==this._$AH&&t!==A,i&&(this._$AH=t);else{let l=t,a,c;for(t=o[0],a=0;a<o.length-1;a++)c=T(this,l[s+a],e,a),c===A&&(c=this._$AH[a]),i||(i=!j(c)||c!==this._$AH[a]),c===p?t=p:t!==p&&(t+=(c??"")+o[a+1]),this._$AH[a]=c}i&&!n&&this.j(t)}j(t){t===p?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},ht=class extends k{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===p?void 0:t}},mt=class extends k{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==p)}},ft=class extends k{constructor(t,e,s,n,o){super(t,e,s,n,o),this.type=5}_$AI(t,e=this){if((t=T(this,t,e,0)??p)===A)return;let s=this._$AH,n=t===p&&s!==p||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==p&&(s===p||n);n&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},gt=class{constructor(t,e,s){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=s}get _$AU(){return this._$AM._$AU}_$AI(t){T(this,t)}};var Se=N.litHtmlPolyfillSupport;Se?.(q,I),(N.litHtmlVersions??(N.litHtmlVersions=[])).push("3.3.3");var Dt=(r,t,e)=>{let s=e?.renderBefore??t,n=s._$litPart$;if(n===void 0){let o=e?.renderBefore??null;s._$litPart$=n=new I(t.insertBefore(D(),o),o,void 0,e??{})}return n._$AI(r),n};var z=globalThis,f=class extends y{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){var e;let t=super.createRenderRoot();return(e=this.renderOptions).renderBefore??(e.renderBefore=t.firstChild),t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Dt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return A}};f._$litElement$=!0,f.finalized=!0,z.litElementHydrateSupport?.({LitElement:f});var Ae=z.litElementPolyfillSupport;Ae?.({LitElement:f});(z.litElementVersions??(z.litElementVersions=[])).push("4.2.2");var we={attribute:!0,type:String,converter:H,reflect:!1,hasChanged:X},Ee=(r=we,t,e)=>{let{kind:s,metadata:n}=e,o=globalThis.litPropertyMetadata.get(n);if(o===void 0&&globalThis.litPropertyMetadata.set(n,o=new Map),s==="setter"&&((r=Object.create(r)).wrapped=!0),o.set(e.name,r),s==="accessor"){let{name:i}=e;return{set(l){let a=t.get.call(this);t.set.call(this,l),this.requestUpdate(i,a,r,!0,l)},init(l){return l!==void 0&&this.C(i,void 0,r,l),l}}}if(s==="setter"){let{name:i}=e;return function(l){let a=this[i];t.call(this,l),this.requestUpdate(i,a,r,!0,l)}}throw Error("Unsupported decorator location: "+s)};function Z(r){return(t,e)=>typeof e=="object"?Ee(r,t,e):((s,n,o)=>{let i=n.hasOwnProperty(o);return n.constructor.createProperty(o,s),i?Object.getOwnPropertyDescriptor(n,o):void 0})(r,t,e)}function B(r){return Z({...r,state:!0,attribute:!1})}var Re="0.1.0-alpha.2";function jt(){console.info(`%c MOUNT-GUARD-CARD %c ${Re} IS INSTALLED `,"color: white; background: #1565c0; font-weight: bold;","color: #1565c0; background: #bbdefb; font-weight: bold;")}function m(r,t,e,...s){let n=`%c MOUNT-GUARD-CARD %c [${t}]`,o=["color: white; background: #1565c0; font-weight: bold;","color: #1565c0; font-weight: bold;"];console[r](n+" "+e,...o,...s)}var qt=10,Ce=2e3,Te=15e3,et=class{constructor(t,e){this.cardName=t;this.fire=e;this.timer=null;this.count=0}schedule(){if(this.timer||(this.count++,this.count>qt))return;let t=Math.min(Ce*this.count,Te);m("info",this.cardName,"Retry %d dans %dms\u2026",this.count,t),this.timer=setTimeout(()=>{this.timer=null,this.fire()},t)}get exhausted(){return this.count>qt}reset(){this.count=0,this.cancel()}cancel(){this.timer&&(clearTimeout(this.timer),this.timer=null)}};var rt=class{constructor(){this.samples=new Map}measure(t,e){let{mount:s,started_at:n,bytes_done:o,bytes_total:i}=t,l=this.samples.get(s);if(!l||l.startedAt!==n)return this.samples.set(s,{startedAt:n,at:e,bytes:o}),null;let a=(e-l.at)/1e3,c=o-l.bytes;if(a<1||c<=0)return null;let h=c/a,d=i-o;return{bytesPerSecond:h,etaSeconds:d>0?d/h:null}}forget(t){this.samples.delete(t)}};var ke={repairing:3,pending:2,degraded:1,ok:0};function It(r){return ke[r.state]??0}function vt(r,t){let e=t.mounts,s=t.show_ok!==!1;return r.filter(n=>!e||e.length===0||e.includes(n.mount)).filter(n=>s||n.state!=="ok").slice().sort((n,o)=>It(o)-It(n)||n.mount.localeCompare(o.mount))}function zt(r,t){return r.length===0?"none-configured":vt(r,t).length===0?"all-healthy":null}var Me="addon_mount_guard/subscribe",st=class{constructor(t,e){this.onRemediation=t;this.onStateChange=e;this.unsubscribe=null;this.generation=0;this.lost=!1}get active(){return this.unsubscribe!==null}async connect(t){if(this.unsubscribe||!t?.connection?.subscribeMessage)return;let e=++this.generation;try{let s=await t.connection.subscribeMessage(n=>{n?.remediation&&this.onRemediation(n.remediation)},{type:Me});if(e!==this.generation){s();return}this.unsubscribe=s,this.lost=!1}catch(s){this.lost=this.lost||!1,m("warn","feed","souscription impossible, repli sur le capteur : %o",s)}this.onStateChange()}disconnect(){if(this.generation++,!!this.unsubscribe){try{this.unsubscribe()}catch(t){m("warn","feed","d\xE9sabonnement en \xE9chec : %o",t)}this.unsubscribe=null}}markLost(){this.unsubscribe=null,this.lost=!0,this.onStateChange()}};function Bt(r,t){let e=new Map;for(let s of r)e.set(s.mount,s);for(let[s,n]of t)e.set(s,n);return[...e.values()]}function Gt({title:r,count:t}){return u`
    <div class="header">
      <div class="title">${r}</div>
      <div class="count">
        ${t===0?"aucune rem\xE9diation":`${t} rem\xE9diation${t>1?"s":""} en cours`}
      </div>
    </div>
  `}function Vt(r){return r?u`
    <div class="notice" role="status">
      <ha-icon icon="mdi:alert-outline"></ha-icon><span>${r}</span>
    </div>
  `:p}function G(r){return u`<ha-card><div class="loader">${r}</div></ha-card>`}function Ft(r){return u`
    <div class="empty">
      ${r==="none-configured"?"Aucun add-on surveill\xE9. Ajoutez-en un depuis la fiche de l'int\xE9gration.":"Tous les montages sont op\xE9rationnels."}
    </div>
  `}var Wt=["o","ko","Mo","Go","To"];function nt(r){if(!Number.isFinite(r)||r<0)return"\u2014";if(r<1e3)return`${Math.round(r)} o`;let t=r,e=0;for(;t>=1e3&&e<Wt.length-1;)t/=1e3,e++;return`${t<10?t.toFixed(1):Math.round(t)} ${Wt[e]}`}function V(r){if(!Number.isFinite(r)||r<0)return"\u2014";let t=Math.floor(r);if(t<60)return`${t} s`;let e=Math.floor(t/60);return e<60?`${e} min ${String(t%60).padStart(2,"0")} s`:`${Math.floor(e/60)} h ${String(e%60).padStart(2,"0")}`}function bt(r){if(!Number.isFinite(r))return"\u2014";let t=Math.max(0,Math.floor(r)),e=Math.floor(t/60);return`${String(e).padStart(2,"0")}:${String(t%60).padStart(2,"0")}`}function ot(r,t=Date.now()){if(!r)return null;let e=Date.parse(r);return Number.isNaN(e)?null:(t-e)/1e3}function $t(r,t=Date.now()){let e=ot(r,t);return e===null?null:-e}function Kt(r,t=48){return r?r.length<=t?r:`\u2026${r.slice(r.length-t+1)}`:""}function Yt(r){let{files_done:t,files_total:e}=r,{bytes_done:s,bytes_total:n}=r,o=null;return n>0?o=s/n:e>0&&(o=t/e),{ratio:o===null?null:Math.min(Math.max(o,0),1),filesDone:t,filesTotal:e,bytesDone:s,bytesTotal:n}}function it(r){return r===null?"":`${Math.round(r*100)} %`}var Jt={local_fallback:["stopping","stashing","reloading","restoring","starting"],stop_only:["stopping","reloading","starting"]},M={stopping:"Arr\xEAt",stashing:"Mise de c\xF4t\xE9",reloading:"Rechargement",restoring:"Rapatriement",rolling_back:"Retour arri\xE8re",starting:"Relance"};function Xt(r){let t=Jt[r.mode]??Jt.local_fallback,e=r.step==="rolling_back",s=r.step_index;return t.map((n,o)=>{let i=o+1,l="todo";return i<s?l="done":i===s&&(l=e?"failed":"active"),{index:i,step:n,label:M[e&&i===s?"rolling_back":n],state:l}})}function Qt(r){return r.state==="repairing"}function Zt(r){return r.state==="degraded"||r.state==="pending"}var Pe={ok:"normal",degraded:"d\xE9grad\xE9",pending:"r\xE9paration due",repairing:"r\xE9paration"};function te(r){return Pe[r]??r}function ee(r){return r.length===0?p:u`
    <details class="history">
      <summary>Historique (${r.length})</summary>
      <table>
        ${r.map(t=>u`
            <tr>
              <td class="at">${new Date(t.at).toLocaleString()}</td>
              <td>${te(t.from)} → ${te(t.to)}</td>
              <td>${t.step?M[t.step]??t.step:""}</td>
              <td>${t.error??""}</td>
            </tr>
          `)}
      </table>
    </details>
  `}function re(r){return u`
    <div class="stepper" role="list">
      ${r.map(t=>u`
          <div class="step ${t.state}" role="listitem" aria-current=${t.state==="active"}>
            <div class="bar"></div>
            <div class="label" title=${t.label}>${t.label}</div>
          </div>
        `)}
    </div>
  `}function se({progress:r,currentFile:t,rate:e}){let s=r.ratio===null?0:r.ratio*100;return u`
    <div class="progress">
      <div
        class="track"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(s)}
      >
        <div class="fill" style="width: ${s}%"></div>
      </div>
      <div class="numbers">
        <span>${r.filesDone} / ${r.filesTotal} fichiers</span>
        <!-- Le pourcentage est celui des OCTETS : il est donc annoncé à côté
             des octets, et non collé au compteur de fichiers, où il se lisait
             comme le leur. Sur un corpus où quelques enregistrements pèsent
             l'essentiel, les deux ratios diffèrent d'un facteur cent. -->
        <span
          >${nt(r.bytesDone)} / ${nt(r.bytesTotal)}
          ${r.ratio===null?"":`(${it(r.ratio)})`}</span
        >
      </div>
      ${e?u`<div class="numbers rate">
            <span>${nt(e.bytesPerSecond)}/s</span>
            <span
              >${e.etaSeconds===null?"":`\u2248 ${V(e.etaSeconds)} restantes`}</span
            >
          </div>`:""}
      ${t?u`<div class="current" title=${t}>${Kt(t)}</div>`:""}
    </div>
  `}var ne={ok:"var(--success-color)",degraded:"var(--warning-color)",pending:"var(--primary-color)",repairing:"var(--primary-color)"},F={ok:"Normal",degraded:"D\xE9grad\xE9",pending:"R\xE9paration en attente",repairing:"R\xE9paration"},Le={started:"d\xE9marr\xE9",stopped:"arr\xEAt\xE9",held:"maintenu arr\xEAt\xE9",unknown:"\xE9tat inconnu"};function oe(r){return r.addons.length===0?"":r.addons.map(t=>`${t.name} \u2014 ${Le[t.state]??t.state}`).join(" \xB7 ")}function ie({remediation:r,now:t,rate:e,showHistory:s,compact:n,onRepair:o,onCancel:i}){let l=r.state==="repairing",a=Xt(r),c=Yt(r);return n?u`
      <div class="mount compact" data-mount=${r.mount}>
        <div class="row">
          <span class="dot" style="--dot-color: ${ne[r.state]}"></span>
          <span class="name">${r.mount}</span>
          <span class="summary">${Oe(r,c.ratio,t)}</span>
        </div>
      </div>
    `:u`
    <div class="mount" data-mount=${r.mount}>
      <div class="row">
        <span class="dot" style="--dot-color: ${ne[r.state]}"></span>
        <span class="name">${r.mount}</span>
        <span class="path">${r.path}</span>
      </div>

      ${oe(r)?u`<div class="addons">${oe(r)}</div>`:""}

      ${l?u`
            ${re(a)}
            ${r.step==="restoring"||r.step==="rolling_back"?se({progress:c,currentFile:r.current_file,rate:e??null}):p}
            <div class="meta">${Ue(r,t)}</div>
          `:u`<div class="meta">${He(r,t)}</div>`}

      ${r.last_error?u`<div class="error">${r.last_error}</div>`:""}

      <div class="actions">
        <mwc-button
          class="repair"
          ?disabled=${!Zt(r)}
          @click=${()=>o(r.mount)}
          >Réparer maintenant</mwc-button
        >
        <mwc-button
          class="cancel"
          ?disabled=${!Qt(r)}
          @click=${()=>i(r.mount)}
          >Annuler</mwc-button
        >
      </div>

      ${s?ee(r.history):p}
    </div>
  `}function Ue(r,t){let e=ot(r.started_at,t),s=r.step?M[r.step]:"",n=`\xE9tape ${r.step_index} sur ${r.step_count}`;return e===null?`${s} \u2014 ${n}`:`${s} \u2014 ${n} \xB7 depuis ${V(e)}`}function He(r,t){if(r.state==="ok")return F.ok;let e=$t(r.next_retry_at,t),s=ot(r.last_incident_at,t),n=[F[r.state]];return s!==null&&n.push(`depuis ${V(s)}`),e!==null&&n.push(`nouvelle tentative dans ${bt(e)}`),n.join(" \xB7 ")}function Oe(r,t,e){if(r.state==="repairing"){let n=r.step?M[r.step]:"",o=it(t);return o?`${n} \xB7 ${o}`:n}if(r.state==="ok")return F.ok;let s=$t(r.next_retry_at,e);return s===null?F[r.state]:`${F[r.state]} \xB7 ${bt(s)}`}var ae=L`
  :host {
    display: block;
  }

  ha-card {
    padding: 0;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 8px;
  }

  .title {
    font-size: 1.15rem;
    font-weight: 500;
    color: var(--primary-text-color);
  }

  .count {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  .notice {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 16px 12px;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    font-size: 0.85rem;
  }

  .notice ha-icon {
    --mdc-icon-size: 18px;
    color: var(--warning-color);
    flex: 0 0 auto;
  }

  .empty {
    padding: 8px 16px 20px;
    color: var(--secondary-text-color);
  }

  .mount {
    padding: 12px 16px;
    border-top: 1px solid var(--divider-color);
  }

  .mount:first-of-type {
    border-top: none;
  }

  .row {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  /* La pastille ne porte jamais de texte : sa couleur est un renfort, et le
     libellé à côté porte l'information. Une pastille seule serait illisible
     pour un daltonien, et le contraste ne distingue pas trois états. */
  .dot {
    flex: 0 0 auto;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--dot-color, var(--disabled-text-color));
  }

  .name {
    font-weight: 500;
    color: var(--primary-text-color);
  }

  .path {
    margin-left: auto;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
    font-family: var(--code-font-family, monospace);
  }

  .addons,
  .meta {
    margin-top: 4px;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  .error {
    margin-top: 6px;
    font-size: 0.85rem;
    color: var(--error-color);
  }

  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 10px;
  }

  mwc-button[disabled] {
    opacity: 0.5;
  }

  .history {
    margin-top: 8px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }

  .history summary {
    cursor: pointer;
    user-select: none;
  }

  .history table {
    margin-top: 6px;
    border-collapse: collapse;
    width: 100%;
  }

  .history td {
    padding: 2px 8px 2px 0;
    vertical-align: top;
  }

  .history .at {
    white-space: nowrap;
    font-family: var(--code-font-family, monospace);
  }

  .compact .row {
    align-items: center;
  }

  .compact .summary {
    color: var(--secondary-text-color);
    font-size: 0.85rem;
    margin-left: auto;
  }

  .loader {
    padding: 24px 16px;
    color: var(--secondary-text-color);
  }
`;var le=L`
  .stepper {
    display: flex;
    align-items: flex-start;
    gap: 4px;
    margin: 10px 0 6px;
  }

  .step {
    flex: 1 1 0;
    min-width: 0;
    text-align: center;
  }

  .bar {
    height: 4px;
    border-radius: 2px;
    background: var(--divider-color);
  }

  .step.done .bar {
    background: var(--success-color);
  }

  .step.active .bar {
    background: var(--primary-color);
  }

  .step.failed .bar {
    background: var(--error-color);
  }

  .step .label {
    margin-top: 4px;
    font-size: 0.7rem;
    color: var(--secondary-text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* L'étape en cours est la seule en couleur de texte pleine : sur une carte
     de cinq cases, mettre tout en évidence revient à ne rien mettre en
     évidence. */
  .step.active .label {
    color: var(--primary-text-color);
    font-weight: 500;
  }

  .step.failed .label {
    color: var(--error-color);
    font-weight: 500;
  }

  .progress {
    margin-top: 8px;
  }

  .track {
    height: 6px;
    border-radius: 3px;
    background: var(--divider-color);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    background: var(--primary-color);
    transition: width 0.3s ease;
  }

  .numbers {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-top: 4px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }

  .numbers.rate {
    margin-top: 2px;
    opacity: 0.85;
  }

  .current {
    margin-top: 2px;
    font-size: 0.78rem;
    color: var(--secondary-text-color);
    font-family: var(--code-font-family, monospace);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    direction: rtl;
    text-align: left;
  }
`;var w="sensor.mount_guard_remediations";var Ne={entity:"Entit\xE9 (capteur des rem\xE9diations)",title:"Titre personnalis\xE9",mounts:"Montages affich\xE9s (vide = tous)",show_ok:"Afficher les montages sains",show_history:"Afficher l'historique",compact:"Mode compact (tableau de bord mural)"},De=[{name:"entity",required:!0,selector:{entity:{domain:"sensor",integration:"addon_mount_guard"}}},{name:"title",selector:{text:{}}},{name:"mounts",selector:{text:{multiple:!0}}},{name:"show_ok",selector:{boolean:{}}},{name:"show_history",selector:{boolean:{}}},{name:"compact",selector:{boolean:{}}}],je=r=>Ne[r.name]??r.name,W=class extends f{constructor(){super(...arguments);this._config={entity:w}}setConfig(e){this._config=e??{entity:w}}createRenderRoot(){return this}render(){return this.hass?u`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${De}
        .computeLabel=${je}
        @value-changed=${this._valueChanged}
      ></ha-form>
    `:u``}_valueChanged(e){let s={...e.detail.value};for(let n of Object.keys(s)){if(n==="entity"){typeof s[n]!="string"&&(s[n]="");continue}let o=s[n];(o===""||o===void 0||o===null)&&delete s[n],Array.isArray(o)&&o.length===0&&delete s[n]}this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:s},bubbles:!0,composed:!0}))}};C([Z({attribute:!1})],W.prototype,"hass",2),C([B()],W.prototype,"_config",2);customElements.get("mount-guard-card-editor")||customElements.define("mount-guard-card-editor",W);var qe=1e3,E=class E extends f{constructor(){super(...arguments);this._now=Date.now();this._id=++E._instances;this._live=new Map;this._retry=new et("card",()=>this.requestUpdate());this._feed=new st(e=>{this._live.set(e.mount,e),this.requestUpdate()},()=>this.requestUpdate());this._rates=new rt;this._tick=null;this._firstUpdateLogged=!1}static getConfigElement(){return document.createElement("mount-guard-card-editor")}static getStubConfig(){return{entity:w}}set hass(e){this._hass=e,this._syncEntityState(),this._feed.connect(e)}get hass(){return this._hass}setConfig(e){if(!e||typeof e!="object")throw m("error","card","setConfig rejet\xE9, config non-objet : %o",e),new Error("Configuration manquante ou invalide");let s=w;typeof e.entity=="string"&&e.entity!==""?s=e.entity:e.entity!==void 0&&e.entity!==null&&e.entity!==""&&m("error","card","'entity' doit \xEAtre une cha\xEEne, re\xE7u %o \u2014 repli sur %s",e.entity,w),this._config={...e,entity:s,mounts:Array.isArray(e.mounts)?e.mounts.map(String):void 0},this._syncEntityState(),m("info","card","#%d setConfig accept\xE9 (entity=%s)",this._id,s)}getCardSize(){return 1+this._remediations().length*2}getGridOptions(){return{columns:12,min_columns:6,rows:"auto",min_rows:2}}connectedCallback(){super.connectedCallback(),this._retry.reset(),this._tick=setInterval(()=>{this._now=Date.now()},qe),this._feed.connect(this._hass)}disconnectedCallback(){this._retry.cancel(),this._tick&&(clearInterval(this._tick),this._tick=null),this._feed.disconnect(),super.disconnectedCallback()}shouldUpdate(e){return e.has("_config")||e.has("_now")?!0:this._entityState!==this._renderedEntityState}render(){return this._render()}updated(){this._renderedEntityState=this._entityState,this._firstUpdateLogged||(this._firstUpdateLogged=!0,m("info","card","#%d premier rendu effectu\xE9 \xE0 t=%dms",this._id,Math.round(performance.now()))),this.dispatchEvent(new CustomEvent("mount-guard-card-update",{bubbles:!0,composed:!0}))}_syncEntityState(){let e=this._config?.entity;this._entityState=e?this._hass?.states[e]:void 0}_remediations(){let e=this._entityState?.attributes??{},s=Array.isArray(e.remediations)?e.remediations:[];return Bt(s,this._live)}_call(e,s){this._hass?.callService("addon_mount_guard",e,{mount:s}).catch(n=>m("error","card","%s(%s) : %o",e,s,n))}_render(){let e=this._config;if(!e)return G("Carte en attente de configuration\u2026");if(!this._hass?.states)return this._retry.schedule(),this._lastTemplate&&!this._retry.exhausted?this._lastTemplate:G("En attente de Home Assistant\u2026");if(!this._entityState)return this._retry.schedule(),this._lastTemplate&&!this._retry.exhausted?this._lastTemplate:G(`Entit\xE9 ${e.entity} introuvable.`);if(this._entityState.state==="unavailable")return this._retry.schedule(),this._lastTemplate&&!this._retry.exhausted?this._lastTemplate:G(`Entit\xE9 ${e.entity} indisponible.`);this._retry.reset();let n=this._remediations(),o=vt(n,e),i=zt(n,e),l=n.filter(c=>c.state==="repairing"||c.state==="pending").length,a=u`
      <ha-card>
        ${Gt({title:e.title??"Montages surveill\xE9s",count:l})}
        ${Vt(this._noticeMessage())}
        ${i?Ft(i):o.map(c=>ie({remediation:c,now:this._now,rate:this._rateFor(c),showHistory:e.show_history===!0,compact:e.compact===!0,onRepair:h=>this._call("repair",h),onCancel:h=>this._call("cancel",h)}))}
      </ha-card>
    `;return this._lastTemplate=a,a}_rateFor(e){return e.state!=="repairing"?(this._rates.forget(e.mount),null):this._rates.measure(e,this._now)}_noticeMessage(){return this._feed.lost&&!this._feed.active?"Connexion temps r\xE9el perdue \u2014 donn\xE9es du dernier relev\xE9.":null}};E.styles=[ae,le],E._instances=0,C([B()],E.prototype,"_config",2),C([B()],E.prototype,"_now",2);var at=E;window.loadCardHelpers?.().catch(r=>{m("warn","card","loadCardHelpers() a \xE9chou\xE9 : %o",r)});var R="mount-guard-card",Ie=5,ce=0;function ze(){if(customElements.get(R)||ce>=Ie)return!1;ce++;try{return customElements.define(R,class extends at{}),m("warn","card","r\xE9-enregistr\xE9 \xE0 t=%dms : le registre d'\xE9l\xE9ments personnalis\xE9s avait \xE9t\xE9 remplac\xE9 depuis le premier enregistrement",Math.round(performance.now())),!0}catch(r){return m("error","card","r\xE9-enregistrement impossible : %o",r),!1}}customElements.get(R)?m("info","card","module d\xE9j\xE0 enregistr\xE9, ce chargement est ignor\xE9"):(customElements.define(R,at),m("info","card","\xE9l\xE9ment enregistr\xE9 \xE0 t=%dms",Math.round(performance.now())));function Be(){let r=0,t=e=>{if(e.localName==="hui-error-card"){let s=e;((s._config??s.config)?.message??"").includes(R)&&(e.dispatchEvent(new CustomEvent("ll-rebuild",{bubbles:!0,composed:!0})),r++);return}for(let s of[...e.shadowRoot?.children??[],...e.children])t(s)};return document.body&&t(document.body),r}for(let r of[0,50,150,400,1e3,2e3,4e3])window.setTimeout(()=>{try{ze();let t=Be();t>0&&m("warn","card","%d carte(s) d'erreur reconstruite(s) apr\xE8s %dms",t,r)}catch(t){m("error","card","r\xE9paration des cartes d'erreur impossible : %o",t)}},r);var lt=window;lt.customCards=lt.customCards??[];lt.customCards.some(r=>r.type===R)||lt.customCards.push({type:R,name:"Add-on Mount Guard",description:"Suit les rem\xE9diations des stockages r\xE9seau tomb\xE9s sous les add-ons"});jt();export{at as MountGuardCard};
